#include <gtk-3.0/gtk/gtk.h>
#include <sys/stat.h>

#include "callbacks.h"

#include <stdio.h>
#include <string.h>
#include <libgen.h>
#include "Types.h"
#include "Format.h"
#include "Functions.h"
#include "Run.h"

#define LOADPROG  "Load Program"
#define SAVEPROG  "Save Program"
#define DUMPVCD   "Dump VCD"
#define SAVECODES "Save Codes"
#define CODESFILE "codes.txt"
#define CODESNAME "Codes"
#define SAVECONN  "Save Connections"
#define CONNFILE  "connections.txt"
#define CONNNAME  "Connections"

gchar *currfile=NULL;
gint  haveprog=0;
extern GtkWidget *wdgts[NWDGTS];
extern int textmode;
extern int testaddr;
extern int breakpoint;

void Error(char *msg)
{
  GtkWidget *error;
  if(textmode)
    {
      fprintf(stderr,"Error: %s \n",msg);
    }
  else
    {
      error=gtk_message_dialog_new(GTK_WINDOW(wdgts[MAINWIN]),
				   GTK_DIALOG_DESTROY_WITH_PARENT,
				   GTK_MESSAGE_ERROR,GTK_BUTTONS_CLOSE,msg);
      gtk_dialog_run(GTK_DIALOG(error));
      gtk_widget_destroy(error);
    }
}

void update_statusbar(char *msg)
{
  if(!textmode)
    {
      gtk_statusbar_pop(GTK_STATUSBAR(wdgts[SBAR]), 1);
      gtk_statusbar_push(GTK_STATUSBAR(wdgts[SBAR]), 1, msg);  
      while(gtk_events_pending())
	gtk_main_iteration();
    }
}

double SESetup(int i)
{
  double result;
  char buf[20];
  int j,k;
  gdouble kr;
  
  gtk_label_set_text(GTK_LABEL(wdgts[PARNAME]),FunList[i].ds);
  gtk_label_set_text(GTK_LABEL(wdgts[PARUNITS]),FunList[i].un);

  gtk_spin_button_set_range(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),FunList[i].min,
			    FunList[i].max);
  gtk_spin_button_set_value(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),
			    FunList[i].cval.fval);
  gtk_spin_button_set_update_policy(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),
				    GTK_UPDATE_IF_VALID);  
  if(strstr(FunList[i].fm,"f"))
    {
      snprintf(buf,20,FunList[i].fm,0.123456789);
      k=strlen(buf)-2;
      for(j=0,kr=1;j<k;j++,kr/=10);	    
      gtk_spin_button_set_digits(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),(guint)k);
      gtk_spin_button_set_increments(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),kr,100*kr);
    }

  gtk_widget_show(wdgts[SENTRY]);

  gtk_dialog_run(GTK_DIALOG(wdgts[SENTRY]));
  result=gtk_spin_button_get_value(GTK_SPIN_BUTTON(wdgts[SNTRSPB]));
  FunList[i].cval.fval=result;
  
  gtk_widget_hide(wdgts[SENTRY]);

  return result;
}


int AESetup(int i)
{
  int result,k;
  char *title, *label;
  int imin, imax;
  
  if(FunList[i].type==TEST_A)
    {
      title="Set Address";
      label="Address";
      imin=MINADDR;
      imax=MAXADDR;
      k=FunList[i].gfib.addr;
    }
  if(FunList[i].type==ENUM_A)
    {
      title="Set Value";
      label="State";
      imin=0;
      imax=FunList[i].gfib.smax-1;
      k=FunList[i].cval.ival;
    }

  gtk_window_set_title(GTK_WINDOW(wdgts[SENTRY]),title);
  gtk_label_set_text(GTK_LABEL(wdgts[PARNAME]),label);
  gtk_label_set_text(GTK_LABEL(wdgts[PARUNITS]),FunList[i].un);

  gtk_spin_button_set_range(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),imin,imax);
  gtk_spin_button_set_value(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),k);

  gtk_widget_show(wdgts[SENTRY]);

  gtk_dialog_run(GTK_DIALOG(wdgts[SENTRY]));
  result=gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(wdgts[SNTRSPB]));

  gtk_widget_hide(wdgts[SENTRY]);

  return result;
}


char *CMDESetup(int i)
{

  char *data;
  gint resp;
  char cval[10];
  

  gtk_window_set_title(GTK_WINDOW(wdgts[CMDENTRY]),"Set Data");
  gtk_label_set_text(GTK_LABEL(wdgts[CMDLABEL]),"Data");

  snprintf(cval,10,"%d",GFIBcs[FunList[i].gfib.addr]);
  gtk_widget_show(wdgts[CMDENTRY]);
  gtk_entry_set_text(GTK_ENTRY(wdgts[CMDENT]),cval);

  do
    resp=gtk_dialog_run(GTK_DIALOG(wdgts[CMDENTRY]));
  while(resp!=GTK_RESPONSE_OK);

  data=g_strdup(gtk_entry_get_text(GTK_ENTRY(wdgts[CMDENT])));

  gtk_widget_hide(wdgts[CMDENTRY]);

  return data;
}

int BESetup(int i)
{

  gboolean data;
  gint resp;


  gtk_window_set_title(GTK_WINDOW(wdgts[BINENTRY]),"Set On/Off");
  gtk_toggle_button_set_active(GTK_TOGGLE_BUTTON(wdgts[BINECHB]),
			       FunList[i].cval.bval);
  
  gtk_widget_show(wdgts[BINENTRY]);

  do      
    resp=gtk_dialog_run(GTK_DIALOG(wdgts[BINENTRY]));
  while(resp!=GTK_RESPONSE_OK);

  data=gtk_toggle_button_get_active(GTK_TOGGLE_BUTTON(wdgts[BINECHB]));
  FunList[i].cval.bval=data;

  gtk_widget_hide(wdgts[BINENTRY]);

  return data;
}

void on_load_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  GtkWidget *openprog;
  GtkFileFilter *filter,*def;
  gchar *file, *path=NULL;
  struct stat fbuf;

  openprog=gtk_file_chooser_dialog_new((const char*)LOADPROG,
				       GTK_WINDOW(wdgts[MAINWIN]),
				       GTK_FILE_CHOOSER_ACTION_OPEN,
				       ("_Cancel"), GTK_RESPONSE_CANCEL,
				       ("_Open"), GTK_RESPONSE_ACCEPT,
				       NULL);

  if(currfile)
    {
      path=(gchar *)dirname(currfile);			  
      gtk_file_chooser_set_current_folder(GTK_FILE_CHOOSER(openprog),
					  (const gchar*)path);
    }
  filter=gtk_file_filter_new();
  gtk_file_filter_add_pattern(filter,"*.mot");
  gtk_file_filter_set_name(filter,"*.mot");
  
  def=gtk_file_filter_new();
  gtk_file_filter_add_pattern(def,"*");
  gtk_file_filter_set_name(def,"All Files");
  
  gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(openprog),filter);
  gtk_file_chooser_add_filter(GTK_FILE_CHOOSER(openprog),def);
  
  gtk_file_chooser_set_filter(GTK_FILE_CHOOSER(openprog),filter);

  if(gtk_dialog_run(GTK_DIALOG(openprog))==GTK_RESPONSE_ACCEPT)
    {
    redo:
      file=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(openprog));

      stat(file,&fbuf);
      if(S_ISREG(fbuf.st_mode))
	{
	  if(ParseProg((char *)file)==0)
	    {
	      if(currfile)
		g_free(currfile);
	      currfile=file;
	      haveprog=TRUE;
	      gtk_widget_set_sensitive(wdgts[RELOADM],TRUE);
	      gtk_widget_set_sensitive(wdgts[SAVEASM],TRUE);
	      gtk_widget_set_sensitive(wdgts[DUMPM],TRUE);
	      gtk_widget_set_sensitive(wdgts[RUNM],TRUE);
	      gtk_widget_set_sensitive(wdgts[RELOADB],TRUE);
	      gtk_widget_set_sensitive (wdgts[RUNB],TRUE);
	      update_statusbar("Program loaded");
	    }
	}
      else
	{
	  Error("Invalid file name!");
	  goto redo;
	}
    }
  gtk_widget_destroy(GTK_WIDGET(openprog));
}


void on_reload_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  if(ParseProg(currfile)==0)
    update_statusbar("Program reloaded");
}


void on_save_as_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  GtkWidget *saveprog;
  char *file;

  if(currfile)
    {
      saveprog=gtk_file_chooser_dialog_new ((const char*)SAVEPROG,GTK_WINDOW(wdgts[MAINWIN]),
					    GTK_FILE_CHOOSER_ACTION_SAVE,
					    ("_Cancel"), GTK_RESPONSE_CANCEL,
					    ("_Save"), GTK_RESPONSE_ACCEPT,
					    NULL);
      gtk_file_chooser_set_do_overwrite_confirmation(GTK_FILE_CHOOSER(saveprog), TRUE);
      gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(saveprog),currfile);
	
      if(gtk_dialog_run(GTK_DIALOG(saveprog))==GTK_RESPONSE_ACCEPT)
	{
	  file=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(saveprog));
	  ASCIIFormat((char *)file,mainprog);
	  update_statusbar("Program saved");
	  g_free (file);
	}
      gtk_widget_destroy(saveprog);
    }
}

void on_dump_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  GtkWidget *dumpvcd;
  char *file;

  if(currfile)
    {
      dumpvcd=gtk_file_chooser_dialog_new ((const char*)DUMPVCD,GTK_WINDOW(wdgts[MAINWIN]),
					    GTK_FILE_CHOOSER_ACTION_SAVE,
					    ("_Cancel"), GTK_RESPONSE_CANCEL,
					    ("_Save"), GTK_RESPONSE_ACCEPT,
					    NULL);
      gtk_file_chooser_set_do_overwrite_confirmation(GTK_FILE_CHOOSER(dumpvcd), TRUE);
      gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(dumpvcd),"dump.vcd");
	
      if(gtk_dialog_run(GTK_DIALOG(dumpvcd))==GTK_RESPONSE_ACCEPT)
	{
	  file=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(dumpvcd));
	  VCDDump((char *)file,mainprog);
	  update_statusbar("VCD dumped");
	  g_free (file);
	}
      gtk_widget_destroy(dumpvcd);
    }
}


void on_run_activate(GtkMenuItem *menuitem,gpointer user_data)
{

  gtk_widget_set_sensitive(wdgts[STOPB],TRUE);
  gtk_widget_set_sensitive(wdgts[STOPM],TRUE);

  gtk_widget_set_sensitive(wdgts[RELOADB],FALSE);
  gtk_widget_set_sensitive(wdgts[RELOADM],FALSE);

  gtk_widget_set_sensitive(wdgts[RUNB],FALSE);
  gtk_widget_set_sensitive(wdgts[RUNM],FALSE);

  gtk_widget_set_sensitive(wdgts[TESTB],FALSE);
  gtk_widget_set_sensitive(wdgts[TESTM],FALSE);
  gtk_widget_set_sensitive(wdgts[SAVEASM],FALSE);

  if(breakpoint)
    Continue();
  else
    RunProg();

  gtk_widget_set_sensitive(wdgts[STOPB],FALSE);
  gtk_widget_set_sensitive(wdgts[STOPM],FALSE);
  
  gtk_widget_set_sensitive(wdgts[RELOADB],TRUE);
  gtk_widget_set_sensitive(wdgts[RELOADM],TRUE);

  gtk_widget_set_sensitive(wdgts[RUNB],TRUE);
  gtk_widget_set_sensitive(wdgts[RUNM],TRUE);

  gtk_widget_set_sensitive(wdgts[TESTB],TRUE);
  gtk_widget_set_sensitive(wdgts[TESTM],TRUE);
  gtk_widget_set_sensitive(wdgts[SAVEASM],TRUE);
}


void on_test_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  int i;
  static int init=0;
  GtkListStore *store;
  GtkTreeIter iter;
  GtkTreeViewColumn *col;
  GtkCellRenderer *renderer=gtk_cell_renderer_text_new();;


  if(!init)
    {
      store=gtk_list_store_new(1,G_TYPE_STRING);
      
      for(i=1;i<FUNLISTSIZE;i++)
	if(FunList[i].id)
	  {
	    gtk_list_store_append(store,&iter);
	    gtk_list_store_set(store,&iter,0,FunList[i].ds,-1);
	  }

      gtk_tree_view_set_model(GTK_TREE_VIEW(wdgts[TTREE]),
			      GTK_TREE_MODEL(store));
      g_object_unref(store);
      col=gtk_tree_view_column_new_with_attributes(NULL,renderer,"text",0,NULL);
      gtk_tree_view_append_column(GTK_TREE_VIEW(wdgts[TTREE]),col);
      gtk_tree_view_set_headers_visible(GTK_TREE_VIEW(wdgts[TTREE]),FALSE);
      gtk_tree_view_columns_autosize(GTK_TREE_VIEW(wdgts[TTREE]));
      init++;
    }

  gtk_widget_show(wdgts[TESTW]);
}

void on_quit_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  if(!textmode)
    gtk_main_quit();
}


void on_about_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  gtk_show_about_dialog(GTK_WINDOW(wdgts[MAINWIN]),
			"program-name","Mot4",
			"copyright","  (C)apirai bai\nM. Prevedelli (2010)",
                        "logo-icon-name","info",
			NULL);
}


void on_codes_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  int i;
  static GtkListStore *store=NULL;

  GtkTreeIter iter;
  GtkTreeViewColumn *col;
  GtkCellRenderer *renderer;

  gtk_window_set_title(GTK_WINDOW(wdgts[CODCON]),CODESNAME);

  if(!store)
    {
      store=gtk_list_store_new(2,G_TYPE_UINT,G_TYPE_STRING);
      
      for(i=1;i<FUNLISTSIZE;i++)
	{
	  if(FunList[i].id)
	    {
	      gtk_list_store_append(store,&iter);
	      gtk_list_store_set(store,&iter,0,FunList[i].id,1,FunList[i].ds,-1);
	    }
	}
    }

  col=gtk_tree_view_get_column(GTK_TREE_VIEW(wdgts[CTREE]),0);
  if(col)
    {
      gtk_tree_view_remove_column(GTK_TREE_VIEW(wdgts[CTREE]),col);
      col=gtk_tree_view_get_column(GTK_TREE_VIEW(wdgts[CTREE]),0);
      gtk_tree_view_remove_column(GTK_TREE_VIEW(wdgts[CTREE]),col);
    }
    
  gtk_tree_view_set_model(GTK_TREE_VIEW(wdgts[CTREE]),GTK_TREE_MODEL(store));
  renderer=gtk_cell_renderer_text_new();

  col=gtk_tree_view_column_new_with_attributes("Code",renderer,"text",0,NULL);
  gtk_tree_view_append_column(GTK_TREE_VIEW(wdgts[CTREE]),col);

  col=gtk_tree_view_column_new_with_attributes("Function",renderer,"text",1,NULL);
  gtk_tree_view_append_column(GTK_TREE_VIEW(wdgts[CTREE]),col);
 
  gtk_tree_view_set_headers_visible(GTK_TREE_VIEW(wdgts[CTREE]),TRUE);
  gtk_tree_view_columns_autosize(GTK_TREE_VIEW(wdgts[CTREE]));
       
  gtk_widget_show(wdgts[CODCON]);
}


void on_connections_activate(GtkMenuItem *menuitem,gpointer user_data)
{
  int i;
  int tb[FUNLISTSIZE];
  char buf[80];
  char *b2;

  
  static GtkListStore *store=NULL;
  GtkTreeIter iter;
  GtkTreeViewColumn *col;
  GtkCellRenderer *renderer;

  gtk_window_set_title(GTK_WINDOW(wdgts[CODCON]),CONNNAME);

  if(!store)
    {
      store=gtk_list_store_new(2,G_TYPE_STRING,G_TYPE_STRING);
      
      for(i=1;i<FUNLISTSIZE;i++)
	{
	  tb[i]=1;
	  if(FunList[i].id)
	    {
	      if(tb[FunList[i].fam])
		{
		  if(FunList[i].cn)
		    {
		      strncpy(buf,FunList[i].cn,80);
		      b2=(gchar *)strchr(buf,':');
		      *b2='\0';
		      b2++;
		      gtk_list_store_append(store,&iter);
		      gtk_list_store_set(store,&iter,0,b2,1,buf,-1);
		      tb[FunList[i].fam]=0;
		    }
		}
	    }
	}
    }
  col=gtk_tree_view_get_column(GTK_TREE_VIEW(wdgts[CTREE]),0);
  if(col)
    {
      gtk_tree_view_remove_column(GTK_TREE_VIEW(wdgts[CTREE]),col);
      col=gtk_tree_view_get_column(GTK_TREE_VIEW(wdgts[CTREE]),0);
      gtk_tree_view_remove_column(GTK_TREE_VIEW(wdgts[CTREE]),col);
    }

  gtk_tree_view_set_model(GTK_TREE_VIEW(wdgts[CTREE]),GTK_TREE_MODEL(store));
  renderer=gtk_cell_renderer_text_new();

  col=gtk_tree_view_column_new_with_attributes("Connection",renderer,"text",
					       0,NULL);
  gtk_tree_view_append_column(GTK_TREE_VIEW(wdgts[CTREE]),col);

  col=gtk_tree_view_column_new_with_attributes("Function",renderer,"text",
					       1,NULL);
  gtk_tree_view_append_column(GTK_TREE_VIEW(wdgts[CTREE]),GTK_TREE_VIEW_COLUMN(col));

  gtk_tree_view_set_headers_visible(GTK_TREE_VIEW(wdgts[CTREE]),TRUE);
  gtk_tree_view_columns_autosize(GTK_TREE_VIEW(wdgts[CTREE]));

  gtk_widget_show(wdgts[CODCON]);    
}


void on_stop_activate(GtkButton *button,gpointer user_data)
{
  RunStop();
}

void on_reset_activate(GtkButton *button,gpointer user_data)
{
  ResetFPGA();
}

void on_codeconn_save_activate(GtkButton *button,gpointer user_data)
{
  const gchar *wname;
  gchar *title, *fname;
  GtkWidget *save;
  int cod;
  FILE *fd;
  int i,j,k,h;
  int tb[FUNLISTSIZE];
  char buf[80];

  wname=gtk_window_get_title(GTK_WINDOW(wdgts[CODCON]));
  cod=(g_ascii_strcasecmp(wname,CODESNAME)==0) ? 1 : 0;
  title=(cod) ? SAVECODES : SAVECONN;
  fname=(cod) ? CODESFILE : CONNFILE;

  save=gtk_file_chooser_dialog_new ((const char*)title,GTK_WINDOW(wdgts[CODCON]),
				    GTK_FILE_CHOOSER_ACTION_SAVE,
				    ("_Cancel"), GTK_RESPONSE_CANCEL,
				    ("_Save"), GTK_RESPONSE_ACCEPT,
				    NULL);
  gtk_file_chooser_set_do_overwrite_confirmation(GTK_FILE_CHOOSER(save), TRUE);
  gtk_file_chooser_set_current_name(GTK_FILE_CHOOSER(save),fname);
  
  if(gtk_dialog_run(GTK_DIALOG(save))==GTK_RESPONSE_ACCEPT)
    {
      fname=gtk_file_chooser_get_filename(GTK_FILE_CHOOSER(save));
      fd=fopen(fname,"w");
      if(cod)
	{
	  fprintf(fd,"                Table of Codes             \n\n");
	  for(i=1;i<FUNLISTSIZE;i++)
	    {
	      if(FunList[i].id)
		fprintf(fd,"(%i)\t%s\n",FunList[i].id,FunList[i].ds);
	    }
	}
      else
	{
	  fprintf(fd,"             Table of Connections          \n\n");	  
	  for(i=1;i<FUNLISTSIZE;i++)
	    {
	      tb[i]=1;
	      if(FunList[i].id)
		{
		  if(tb[FunList[i].fam])
		    {
		      k=strlen(FunList[i].cn);
		      for(j=0;j<k;j++)
			{
			  if(FunList[i].cn[j]!=':')
			    buf[j]=FunList[i].cn[j];
			  else
			    break;
			}
		      for(h=j;h<30;buf[h++]=' ');
		      for(h=0;h<k-j;h++)
			buf[30+h]=FunList[i].cn[j+h+1];
		      buf[30+h+1]='\0';
		      fprintf(fd,"%s\n",buf);
		      tb[FunList[i].fam]=0;
		    }
		}
	    }
	}
      fclose(fd);
    }
  gtk_widget_destroy(save);
}


void on_test_exec_activate(GtkButton *button,gpointer user_data)
{
  GtkTreeSelection *select;
  GtkTreeIter iter;
  GtkTreeModel *model;
  gchar *sel;

  select=gtk_tree_view_get_selection(GTK_TREE_VIEW(wdgts[TTREE]));

  if(gtk_tree_selection_get_selected(select,&model,&iter))
    gtk_tree_model_get(model,&iter,0,&sel,-1);

  RunTest(sel);
}

void on_testad_activate(GtkButton *button,gpointer user_data)
{

  gtk_window_set_title(GTK_WINDOW(wdgts[SENTRY]),"Set Address");
  gtk_label_set_text(GTK_LABEL(wdgts[PARNAME]),"Address");
  gtk_label_set_text(GTK_LABEL(wdgts[PARUNITS])," ");

  gtk_spin_button_set_range(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),MINADDR,MAXADDR);
  gtk_spin_button_set_value(GTK_SPIN_BUTTON(wdgts[SNTRSPB]),testaddr);

  gtk_widget_show(wdgts[SENTRY]);

  gtk_dialog_run(GTK_DIALOG(wdgts[SENTRY]));
  testaddr=gtk_spin_button_get_value_as_int(GTK_SPIN_BUTTON(wdgts[SNTRSPB]));

  gtk_widget_hide(wdgts[SENTRY]);
}


void on_clear_activate(GtkButton *button,gpointer user_data)
{
  gtk_entry_set_text(GTK_ENTRY(wdgts[CMDENT]),"0");  
}


