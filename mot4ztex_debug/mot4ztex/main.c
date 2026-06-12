#include <stdio.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <string.h>
#include <signal.h>
#include <signal.h>
#include <libgen.h>

#include <gtk-3.0/gtk/gtk.h>

#include "callbacks.h"

#include "Types.h"
#define UIFILE "mot4.ui"

GtkWidget *wdgts[NWDGTS];
cmdload *cmdlist;  
cmdloadbuff *cmdlistbuff;

int textmode=0;
int testaddr=-1;
int exttrig=FALSE;
int fd;

extern int running;
extern void RunStop(void);
extern void ResetFPGA(void);
extern int ParseProg(char *);
extern void RunProg(void);

void clearlock(int dummy)
{
  if(running)
    {
      RunStop();
      fprintf(stderr,"received <Ctrl> C\n");
    }
  lockf(fd,F_ULOCK,0);
  close(fd);  
  exit(-1);
}

int main(int argc,char *argv[])
{
  char *p,c;
  char *vcdfn;
  int i;
  GtkBuilder *builder;
  char *progname=NULL;
  
  fd=open(LOCKFILE,O_WRONLY | O_CREAT,S_IWUSR);
  if(lockf(fd,F_TLOCK,0))
    return -1;

  signal(SIGINT,clearlock);
  signal(SIGTERM,clearlock);

  while(1) 
    {
      c=getopt(argc,argv,"erf:");
      if (c==-1)
	break;
      switch(c)
	{
	case 'e':
	  exttrig=TRUE;
	  break;
	  
	case 'r':
	  ResetFPGA();
	  return 0;
	  break;

	case 'f':
	  progname=strdup(optarg);
	  break;
	  
	default:
	  fprintf(stderr,"usage         : %s -f prog.mot\n",TPROGNAME);
	  fprintf(stderr,"other options : -e for external trigger\n");
	  fprintf(stderr,"              : -r fpga reset then quits\n");
	  return -1;
	}
    }
  
  InitFunList();

  cmdlist=(cmdload *)malloc(sizeof(cmdload)*MAXNACT);
  if(!cmdlist)
    return -1;

  cmdlistbuff=(cmdloadbuff *)malloc(sizeof(cmdloadbuff)*MAXNBUFF);
  if(!cmdlistbuff)
    return -1;
  else
    for(i=0;i<MAXNBUFF;i++)
      memcpy(cmdlistbuff[i].cmd,CMD_LOAD,2);
  
  p=argv[0]+strlen(argv[0])-strlen(TPROGNAME);
  if(strcmp(p,CPROGNAME)==0 || strcmp(p,TPROGNAME)==0) 
//AB  if(strcmp(p,TPROGNAME)==0)
    {
      if(strcmp(p,TPROGNAME)==0)
	textmode++;
//AB      textmode++;
      if(!progname)
	{
	  fprintf(stderr,"Please specify a file to run with -f file.mot\n");
	  lockf(fd,F_ULOCK,0);
	  close(fd);
	  return -1;
	}
      if(!ParseProg(progname))
	{
	  if(textmode)
	    RunProg();
	  else
	    {
	      vcdfn=basename(progname);
	      p=strrchr(vcdfn,'.');

	      if(p)
		{
		  strcpy(p,".vcd");
		  VCDDump(vcdfn,mainprog);
		}
	      lockf(fd,F_ULOCK,0);
	      return 0;
	    }
	}
//AB      if(!ParseProg(progname))
//AB	RunProg();
    }
  else
    {
      //      gtk_set_locale();
      gtk_init(&argc,&argv);

      builder=gtk_builder_new();
      gtk_builder_add_from_file(builder,UIFILE,NULL);
      gtk_builder_connect_signals(builder,NULL);
      
      wdgts[MAINWIN]=GTK_WIDGET(gtk_builder_get_object(builder,"mot4"));
      wdgts[SBAR]=GTK_WIDGET(gtk_builder_get_object(builder,"statusbar1"));

      wdgts[SENTRY]=GTK_WIDGET(gtk_builder_get_object(builder,"sentry"));
      wdgts[PARNAME]=GTK_WIDGET(gtk_builder_get_object(builder,"parname"));
      wdgts[PARUNITS]=GTK_WIDGET(gtk_builder_get_object(builder,"parunits"));
      wdgts[SNTRSPB]=GTK_WIDGET(gtk_builder_get_object(builder,"spinbutton1"));

      wdgts[CMDENTRY]=GTK_WIDGET(gtk_builder_get_object(builder,"cmdentry"));
      wdgts[CMDLABEL]=GTK_WIDGET(gtk_builder_get_object(builder,"label19"));
      wdgts[CMDENT]=GTK_WIDGET(gtk_builder_get_object(builder,"entry2"));

      wdgts[BINENTRY]=GTK_WIDGET(gtk_builder_get_object(builder,"binentry"));
      wdgts[BINECHB]=GTK_WIDGET(gtk_builder_get_object(builder,"checkbutton1"));

      wdgts[RELOADB]=GTK_WIDGET(gtk_builder_get_object(builder,"button13"));
      wdgts[TESTB]=GTK_WIDGET(gtk_builder_get_object(builder,"button14"));
      wdgts[RUNB]=GTK_WIDGET(gtk_builder_get_object(builder,"button15"));
      wdgts[STOPB]=GTK_WIDGET(gtk_builder_get_object(builder,"button16"));
      wdgts[RESETB]=GTK_WIDGET(gtk_builder_get_object(builder,"button17"));

      wdgts[RELOADM]=GTK_WIDGET(gtk_builder_get_object(builder,"reload_m"));
      wdgts[TESTM]=GTK_WIDGET(gtk_builder_get_object(builder,"test_m"));
      wdgts[TESTADM]=GTK_WIDGET(gtk_builder_get_object(builder,"testad_m"));
      wdgts[SAVEASM]=GTK_WIDGET(gtk_builder_get_object(builder,"save_as_m"));
      wdgts[DUMPM]=GTK_WIDGET(gtk_builder_get_object(builder,"dump_m"));
      wdgts[RUNM]=GTK_WIDGET(gtk_builder_get_object(builder,"run_m"));
      wdgts[STOPM]=GTK_WIDGET(gtk_builder_get_object(builder,"stop_m"));

      wdgts[TESTW]=GTK_WIDGET(gtk_builder_get_object(builder,"test"));
      wdgts[TTREE]=GTK_WIDGET(gtk_builder_get_object(builder,"treeview1"));

      wdgts[CODCON]=GTK_WIDGET(gtk_builder_get_object(builder,"codeconn"));
      wdgts[CTREE]=GTK_WIDGET(gtk_builder_get_object(builder,"treeview2"));

      g_object_unref(G_OBJECT(builder));

      gtk_statusbar_push(GTK_STATUSBAR(wdgts[SBAR]),1,"Idle");

      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[RELOADB]),FALSE);
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[RUNB]),FALSE);
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[STOPB]),FALSE);
      gtk_widget_set_sensitive(wdgts[RESETB],TRUE);

      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[RELOADM]),FALSE);
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[SAVEASM]),FALSE);
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[DUMPM]),FALSE);
#ifdef TESTGUI
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[TESTADM]),TRUE);
#else
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[TESTADM]),FALSE);
#endif
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[RUNM]),FALSE);
      gtk_widget_set_sensitive(GTK_WIDGET(wdgts[STOPM]),FALSE);


      gtk_widget_show(wdgts[MAINWIN]);
  
      gtk_main();
    }
  if(running)
    RunStop();
  lockf(fd,F_ULOCK,0);
  close(fd);
  free(cmdlist);
  free(cmdlistbuff);

  return 0;
}
