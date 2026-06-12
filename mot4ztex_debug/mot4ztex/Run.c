#include "Types.h"
#include "DLList.h"
#include "Format.h"
#include "Compile.h"
#include <stdio.h>
#include <string.h>
#include <values.h>
#include <stdlib.h>
#include <unistd.h>
#include <time.h>
#include <byteswap.h>
#include <libusb-1.0/libusb.h>

#include "callbacks.h"
#include "Functions.h"

extern int yydebug;
extern int yychar;
extern prog* yypprog;
extern FILE *yyin;  
extern int yyparse(void);
extern int textmode;
extern int testaddr;
extern int exttrig;



int running=FALSE;
int breakpoint=FALSE;
libusb_device_handle *hdev;
prog *mainprog;
static int iface_claimed=FALSE;

#define RETRY 10

extern GtkWidget *wdgts[NWDGTS];

static void usb_cleanup(void)
{
  if(hdev)
    {
      if(iface_claimed)
	{
	  libusb_release_interface(hdev,0);
	  iface_claimed=FALSE;
	}
      libusb_close(hdev);
      hdev=NULL;
    }
  libusb_exit(NULL);
}

static int usb_fail(const char *step, int ret, int transferred, int expected)
{
  if(ret < 0)
    fprintf(stderr,"USB failure at %s: %s (%d), transferred=%d expected=%d\n",
	    step,libusb_error_name(ret),ret,transferred,expected);
  else
    fprintf(stderr,"USB short transfer at %s: transferred=%d expected=%d\n",
	    step,transferred,expected);
  running=FALSE;
  breakpoint=FALSE;
  return PROGLDERR;
}

static int bulk_xfer_exact(unsigned char endpoint, unsigned char *data, int len,
			   int *transferred, const char *step)
{
  int ret;

  *transferred=0;
  ret=libusb_bulk_transfer(hdev,endpoint,data,len,transferred,USB_TMO);
  if(ret<0 || *transferred!=len)
    return usb_fail(step,ret,*transferred,len);
  return 0;
}

static int usb_open_fpga(int claim_interface)
{
  int ret;

  libusb_init(NULL);
  hdev=libusb_open_device_with_vid_pid(NULL,FPGA_VID,FPGA_PID);
  if(!hdev)
    {
      fprintf(stderr,"USB failure at open: device %04x:%04x not found\n",
	      FPGA_VID,FPGA_PID);
      usb_cleanup();
      return PROGLDERR;
    }

  if(claim_interface)
    {
      ret=libusb_claim_interface(hdev,0);
      if(ret<0)
	{
	  fprintf(stderr,"USB failure at claim interface 0: %s (%d)\n",
		  libusb_error_name(ret),ret);
	  usb_cleanup();
	  return PROGLDERR;
	}
      iface_claimed=TRUE;
    }

  return 0;
}

void ResetFPGA(void)
{
  unsigned char c;
  int ret,n=0;
  
  if(usb_open_fpga(FALSE))
    return;
  //reset fpga
  ret=libusb_control_transfer(hdev,0x40,0x31,0,0,0,0,USB_TMO);
  if(ret<0)
    fprintf(stderr,"USB failure at reset vendor command: %s (%d)\n",
	    libusb_error_name(ret),ret);
  c=1;
  ret=libusb_control_transfer(hdev,0x40,0xA0,0xE600,0,&c,1,USB_TMO);
  if(ret<0 || ret!=1)
    fprintf(stderr,"USB failure at reset CPUCS=1: %s (%d), transferred=%d expected=1\n",
	    ret<0 ? libusb_error_name(ret) : "SHORT",ret,ret<0 ? n : ret);
  c=0;
  ret=libusb_control_transfer(hdev,0x40,0xA0,0xE600,0,&c,1,USB_TMO);
  if(ret<0 || ret!=1)
    fprintf(stderr,"USB failure at reset CPUCS=0: %s (%d), transferred=%d expected=1\n",
	    ret<0 ? libusb_error_name(ret) : "SHORT",ret,ret<0 ? n : ret);
  usb_cleanup();
  
  if(!textmode)
    gtk_statusbar_push(GTK_STATUSBAR(wdgts[SBAR]),1,"Resetting FPGA");
  sleep(1);  
  if(textmode)
    fprintf(stderr,"FPGA reset complete\n");
  else
    gtk_statusbar_push(GTK_STATUSBAR(wdgts[SBAR]),1,"FPGA reset complete");
}

int Exec(int idx)
{
  int i,j,k,n,ret;
  char status[40];
  unsigned char cmd[2],ans[4];
  struct timespec req;
  div_t dr;

  req.tv_sec=0;
  req.tv_nsec=STARTDELAY;
  
#ifndef DEBUG
  if(usb_open_fpga(TRUE))
    return PROGLDERR;
#endif
  
  //load
  k=0;
  dr=div(idx,MAXNBUFF);
  snprintf(status,40,"Loading..");
  update_statusbar(status);
  if(dr.quot)
    for(i=0;i<dr.quot;i++)
      {
	for(j=0;j<MAXNBUFF;j++,k++)
	  {
	    cmdlistbuff[j].addr=bswap_32(cmdlist[k].addr);
	    cmdlistbuff[j].data=bswap_64(cmdlist[k].data);
	  }
	ret=bulk_xfer_exact(EPOUT,(unsigned char *)cmdlistbuff,
			    MAXNBUFF*sizeof(cmdloadbuff),&n,"load chunk");
	if(ret)
	  goto fail;
      }

  if(dr.rem)
    {
      for(i=0;i<dr.rem;i++,k++)
	{
	  cmdlistbuff[i].addr=bswap_32(cmdlist[k].addr);
	  cmdlistbuff[i].data=bswap_64(cmdlist[k].data);
	}
#ifndef DEBUG
      ret=bulk_xfer_exact(EPOUT,(unsigned char *)cmdlistbuff,
			  dr.rem*sizeof(cmdloadbuff),&n,"load tail");
      if(ret)
	goto fail;
#endif
    }

#ifndef DEBUG
  memcpy(cmd,CMD_LDDONE,2);
  ret=bulk_xfer_exact(EPOUT,cmd,2,&n,"send load done");
  if(ret)
    goto fail;

  if(exttrig)
    memcpy(cmd,CMD_EXTTRG,2);
  else
    memcpy(cmd,CMD_INTTRG,2);
  ret=bulk_xfer_exact(EPOUT,cmd,2,&n,"send trigger mode");
  if(ret)
    goto fail;

  nanosleep(&req,NULL);
  memcpy(cmd,CMD_TRIG,2);
  ret=bulk_xfer_exact(EPOUT,cmd,2,&n,"send trigger");
  if(ret)
    goto fail;
  running=TRUE;

  req.tv_nsec=STATUSDELAY;
  memcpy(cmd,CMD_STATUS,2);
  do
    {
      nanosleep(&req,NULL);
      ret=bulk_xfer_exact(EPOUT,cmd,2,&n,"status request");
      if(ret)
	goto fail;
      
      nanosleep(&req,NULL);
      ret=bulk_xfer_exact(EPIN,ans,4,&n,"status response");
      if(ret)
	goto fail;

      i=ans[1];
      i<<=8;
      i|=ans[2];
      i<<=8;
      i|=ans[3];
      
      switch(ans[0])
	{
	case ST_RUNNING:
	  snprintf(status,40,"Instr. %d out of %d",i,idx);
	  update_statusbar(status);
	  breakpoint=FALSE;
	  break;	  	

	case ST_WAIT:
	  snprintf(status,40,"Waiting for ext. trigger");
	  update_statusbar(status);
	  break;
	  
	case ST_BREAK:
	  breakpoint=TRUE;
	  snprintf(status,40,"Breakpoint at instr. %d",i);
	  update_statusbar(status);
	  if(!textmode & !exttrig)
	    {
	      gtk_widget_set_sensitive (wdgts[RUNB],TRUE);
	      gtk_widget_set_sensitive (wdgts[RUNM],TRUE);
	      gtk_widget_set_sensitive (wdgts[STOPB],FALSE);
	      gtk_widget_set_sensitive(wdgts[STOPM],FALSE);
	    }
	  
	  break;
	}
    }
  while(ans[0]!=ST_IDLE);
  running=FALSE;
  usb_cleanup();
#endif
  return PROGTERM;

 fail:
  if(hdev)
    {
      memcpy(cmd,CMD_HALT,2);
      libusb_bulk_transfer(hdev,EPOUT,cmd,2,&n,USB_TMO);
      libusb_clear_halt(hdev,EPOUT);
      libusb_clear_halt(hdev,EPIN);
    }
  usb_cleanup();
  return PROGLDERR;
}

int ParseProg(char * fname)
{
  int er=0;
  
#ifdef PARSERDBG
  yydebug=1;             /* turn on parser debug */
#endif
  yypprog=PClear(yypprog);
  yyin=fopen(fname,"r");
  er=yyparse();
  fclose(yyin);
  if(er)
    {
      Error("Parse Error: Must quit!");
      on_quit_activate(NULL,NULL);
    }
  if(!yypprog)
    {
      Error("This is not a program!");
      return NOTAPROG;
    }
  er=0;
  mainprog=PClear(mainprog);
  mainprog=PCopy(yypprog, &er);
  switch(er)
    {
    case DLLECODE:
      Error("Wrong code");
      mainprog=PClear(mainprog);      
      break;
    case DLLETIME:
      Error("Time too LARGE");
      mainprog=PClear(mainprog);
      break;
    case DLLERANGE:
      Error("Parameter out of Range");
      mainprog=PClear(mainprog);
      break;
    case DLLERNSC:
      Error("Cannot ramp non Scalar/Enum Actions");
      mainprog=PClear(mainprog);
      break;
    case DLLESHORT:
      Error("Step too short in RAMP");
      mainprog=PClear(mainprog);
      break;
    case DLLEROVL:
      Error("RAMP Overlap");
      mainprog=PClear(mainprog);
      break;
    case DLLERSOVL:
      Error("RAMP and Scalar action overlap");
      mainprog=PClear(mainprog);
      break;
    case DLLERTLG:
      Error("RAMP too long");
      mainprog=PClear(mainprog);
      break;
    case DLLERLOG:
      Error("RAMPLOG crosses zero");
      mainprog=PClear(mainprog);
      break;
    case DLLEGADDR:
      Error("GPIB Address out of Range");
      mainprog=PClear(mainprog);
      break;
    case DLLELOOP:
      Error("Invalid Loop");
      mainprog=PClear(mainprog);
      break;
    case DLLEZINT:
      Error("Time in inner can not be zero");
      mainprog=PClear(mainprog);
      break;
    case DLLESAMET:
      Error("Simultaneous incompatible actions");
      mainprog=PClear(mainprog);
      break;
    }
  if(er)
    yypprog=PClear(yypprog);
  return er;
}

void RunTest(char *sel)
{
  int i=1,idx;
  prog *tp;
  loop tlp;
  innerlist *tnl;
  inneract tna;

  if(running)
    {
      Error("Stop running program first");
      return;
    }
  while(i<FUNLISTSIZE)
    {
      if(FunList[i].id)
	{
	  if(strcmp(sel,FunList[i].ds))
	    i++;
	  else
	    break;
	}
      else i++;
    }
  tna.id=FunList[i].id;
  tna.cval.fval=MAXDOUBLE;
  tna.en=TRUE;
  tna.block=FALSE;
  tna.time=INITDELAY;
  tna.ramp=FALSE;
  tna.cval.sval=NULL;
  switch(FunList[i].type)
    {
    case BINARY_A:
      tna.cval.bval=BESetup(i);
      break;
    case ENUM_A:
      tna.cval.ival=AESetup(i);
      break;
    case SCALAR_A:
      tna.cval.fval=SESetup(i);
      break;
    case TEST_A:
      tna.addr=FunList[i].gfib.addr=AESetup(i);
      tna.cval.sval=CMDESetup(i);
      tna.cval.ival=strtol(tna.cval.sval,NULL,0);
      break;
    }
#ifdef TEST
  if(FunList[i].type!=TEST_A && testaddr>0)
    tna.addr=FunList[i].gfib.addr=testaddr;
#endif


  tnl=NInsert(NULL,tna);
  tlp.cmt=NULL;
  tlp.il=NULL;
  tlp.nl=tnl;
  tlp.en=TRUE;
  tlp.iter=1;
  tp=PInsert(NULL,tlp);
  idx=Compile(tp);
  switch(Exec(idx))
    {
    case PROGLDERR:
      Error("   USB error\n Check your Hardware!");
      break;
    }
  PClear(tp);
  free(tna.cval.sval);
  update_statusbar("Test finished!");
}


void RunStop(void)
{
  unsigned char cmd[2];
  int n;

  memcpy(cmd,CMD_HALT,2);
  libusb_bulk_transfer(hdev,EPOUT,cmd,2,&n,USB_TMO);
  running=FALSE;
  breakpoint=FALSE;
}

void RunProg(void)
{
  int idx, res=0;
  
  idx=Compile(mainprog);

  if(idx<0)
    {
      Error("Program too long!");
      return;
    }
  if(idx)
    {
      res=Exec(idx);
      switch(res)
	{
	case PROGTERM:
	  update_statusbar("Program finished!");
	  break;
	case PROGLDERR:
	  Error("   USB error\n Check your Hardware!");
	  break;
	}
    }
}

void Continue(void)
{
  unsigned char cmd[2];
  int n;
  
  if(!exttrig)
    {
      memcpy(cmd,CMD_TRIG,2);
      libusb_bulk_transfer(hdev,EPOUT,cmd,2,&n,USB_TMO);
      breakpoint=FALSE;
    }
}


