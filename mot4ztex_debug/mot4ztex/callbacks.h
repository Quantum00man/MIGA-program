#include <gtk-3.0/gtk/gtk.h>

#define MAINWIN  0
#define SBAR     1

#define SENTRY   2
#define PARNAME  3
#define PARUNITS 4
#define SNTRSPB  5

#define CMDENTRY 6
#define CMDLABEL 7
#define CMDENT   8

#define BINENTRY 9
#define BINECHB 10

#define RELOADB 11
#define RUNB    12
#define TESTB   13
#define STOPB   14
#define RESETB  15

#define RELOADM 16
#define SAVEASM 17
#define DUMPM   18
#define RUNM    19
#define TESTM   20
#define TESTADM 21
#define STOPM   22

#define TESTW   23
#define TTREE   24

#define CODCON  25
#define CTREE   26

#define NWDGTS  27

void Error(char *msg);

void update_statusbar(char *msg);

double SESetup(int i);

int AESetup(int i);

char *CMDESetup(int i);

int BESetup(int i);

void on_load_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_reload_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_save_as_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_dump_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_run_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_test_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_quit_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_about_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_codes_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_connections_activate(GtkMenuItem *menuitem,gpointer user_data);
void on_stop_activate(GtkButton *button,gpointer user_data);
void on_reset_activate(GtkButton *button,gpointer user_data);
void on_codeconn_save_activate(GtkButton *button,gpointer user_data);
void on_test_exec_activate(GtkButton *button,gpointer user_data);
void on_cmdentry_clear_activate(GtkButton *button,gpointer user_data);
void on_cmdentry_ok_activate(GtkButton *button,gpointer user_data);
