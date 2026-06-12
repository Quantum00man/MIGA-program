/* Types.h: defines few structures for Mot */
/* M. Prevedelli (2009)  */

#ifndef _Types_
#define _Types_

#include <stdint.h>

#define CLOCKPERIOD  100ULL                 /* 10 MHz clock */ 

#define TPROGNAME "tmot4"
#define CPROGNAME "cmot4"
#define LOCKFILE  "/var/lock/mot4"

#define ADDRSPACE 128
#define MINADDR   1
#define MAXADDR 127
#define FUNLISTSIZE 100 
#define MAXNACT  0x800000   /* 8M instr */
#define MAXNBUFF 0x10000   /* 64k instr */

#ifndef TRUE
#define TRUE 1
#define FALSE 0
#endif

#define PROGSTART   0
#define PROGTERM    1
#define PROGRUN     2
#define PROGLDERR   3
#define PROGBREAK   4

#define SIMPLE_A    1           /* Actions without parameters */
#define BINARY_A    2           /* Actions with binary choices */
#define ENUM_A      4           /* Actions with a single integer parameter in a set */
#define SCALAR_A    8           /* Actions with a single real parameter */
#define TEST_A     16           /* Actions with a single real parameter */

#define RAMPLIN 1
#define RAMPLOG 2

#define MAXNS          32000000000000000ULL         /* one year of nanoseconds */ 
#define MINDELAY       CLOCKPERIOD                  /* 1 clock cycles */
#define INITDELAY      CLOCKPERIOD                  /* 1 clock cycles */
#define MAXDUMMYTIME  (0xFFFFFFFFFULL*CLOCKPERIOD)  /* insert a dummy action every ~ 6872 s (@10MHz) */
#define STARTDELAY     10000                        /* start delay (ns) */
#define STATUSDELAY   10000000                      /* status delay (ns) */

#define FPGA_VID 0x221A
#define FPGA_PID 0x0100
#define EPOUT 0x6
#define EPIN  0x82


//usb commands

#define CMD_LOAD      "DA"
#define CMD_LDDONE    "PL"
#define CMD_EXTTRG    "EX"
#define CMD_INTTRG    "IN"
#define CMD_STATUS    "ST"
#define CMD_RESET     "RS" 
#define CMD_TRIG      "TR"
#define CMD_HALT      "HA"

#define USB_TMO       10000

//status byte
#define ST_IDLE    'I'
#define ST_WAIT    'W'
#define ST_RUNNING 'R'
#define ST_BREAK   'B'

//op byte
#define OP_BREAK  (1ULL<<60) 
#define OP_NOP    (1ULL<<61)
#define OP_END    (1ULL<<63) 

#pragma pack(1)
typedef struct {
  char cmd[2];
  uint32_t addr;
  uint64_t data;
} cmdloadbuff;
#pragma pack()

typedef struct {
  uint32_t addr;
  uint64_t data;
} cmdload;

typedef struct cval_struct{
  double fval;
  int ival;
  int bval;
  char *sval; 
} val;

typedef struct gfib_struct{
  unsigned addr;
  unsigned mask;
  int smax;
} gfib_t;


typedef struct act_struct{
  char       *ds;	        /* Description (es. "B Field") */
  char 	     *cn;	        /* Connection (es. "Board X, Bit Y") */
  unsigned   type;              /* type of action (es. SIMPLE_A etc.) */
  unsigned   id;                /* Unique positive integer used as ID */   
  gfib_t     gfib;              /* Address on the GFIB BUS */   
  unsigned   fam;               /* Family: actions of the same family 
                                   can be executed at the same time
				   (es. dig. signals on the same board */
  double     min;	        /* Min. Value */
  double     max;	        /* Max. Value */
  val        cval;	        /* Current Value. Used for compiling */
  char       *un;	        /* Units */
  char       *fm;               /* Format string for float i.e. "%3.6f" */
  unsigned  (*compile)(val);    /* Compute actual parameter from a val  */
} action;

typedef struct initact_struct{
  unsigned id;             /* id for the action */ 
  val cval;                /* value for scalar actions */
  int en;                  /* Enabled ? */       
  int block;               /* block here? */
  unsigned addr;           /* addr for test actions */
} initact;
 
typedef struct initlist_struct {     
  initact ia;              /* Double Linked List */  
  struct initlist_struct *prev;             
  struct initlist_struct *next;             
} initlist;

typedef struct inneract_struct{
  unsigned id;              /* id for the action */ 
  val cval;                 /* value for scalar actions */
  int en;                   /* Enabled ? */
  int block;                /* block here? */
  unsigned addr;            /* addr for test actions */
  unsigned ord;             /* order if many at the same time */
  unsigned long long time;  /* Execution time */
  int ramp;                 /* Is a ramp ? */
  double fval;              /* final value for a ramp */
  unsigned long long rt;    /* ramp time */
  unsigned steps;           /* number of steps for a ramp */
  
} inneract;

typedef struct innerlist_struct{     /* Double Linked List */ 
  inneract na;                
  struct innerlist_struct *prev;             
  struct innerlist_struct *next;             
} innerlist;

typedef struct loop_struct{
  char *cmt;                /* comment */ 
  initlist *il;             /* pointer to initlist */
  innerlist *nl;            /* pointer to innerlist */
  int en;                   /* Enabled ? */
  unsigned iter;            /* number of iterations */
} loop;

typedef struct prog_struct{     /* Double Linked List */ 
  loop lp;                
  struct prog_struct *prev;             
  struct prog_struct *next;             
} prog;


/* Global Variables and functions*/

extern void InitFunList(void);
extern action FunList[FUNLISTSIZE];
extern unsigned GFIBcs[ADDRSPACE];
extern prog *mainprog;
extern cmdload *cmdlist;
extern cmdloadbuff *cmdlistbuff;

#endif /* _Types_ */








