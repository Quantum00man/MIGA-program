/* parser for MOT2 */
/* M. Prevedelli 1998 */

%{
#include<stdio.h>
#include<string.h>
#include<malloc.h>
#include<values.h>
#include<limits.h>
#include "Types.h"
#include "DLList.h"

#define MAXCMTSIZE 1000
char cmtline[MAXCMTSIZE];
prog *yypprog=NULL;         
extern int yylex();
int yyerror(char *);
 
%}

%union {
char cval;
char *sval;
unsigned ival;
unsigned bval;
long long lval;
double fval;
initact ia;
inneract na;
initlist *il;
innerlist *nl;
loop	lp;
}

%token <ival> CODE NUM STATE ADDR DATA BIN 
%token <ival> STP BL EL BC EC BI EI BN EN IT RMP GFIB DISAB BR
%token <cval> CHR
%token <fval> PARM
%token <lval> TIME

%type <ia> initline ilbody isimple ibinary ienum iscalar itest
%type <na> innerline nlbody nsimple nbinary nenum nscalar ntest ramp
%type <sval> comment commentbody
%type <il> init initbody
%type <nl> inner innerbody
%type <lp> loop loopbody
%type <ival> iter

%%

input:    /* empty */ 
 	| input loop {yypprog=PInsert(yypprog,$<lp>2);}
;	

loop:	  BL loopbody EL         {$<lp>$ = $<lp>2; $<lp>$.en = TRUE;}
	| BL DISAB loopbody EL   {$<lp>$ = $<lp>3; $<lp>$.en = FALSE;}
;

loopbody: comment init inner iter {$<lp>$.cmt = $<sval>1; 
				   $<lp>$.il = $<il>2; 
                                   $<lp>$.nl = $<nl>3;
				   $<lp>$.iter = $<ival>4;}
	| init inner iter          {$<lp>$.cmt = NULL; 
				   $<lp>$.il = $<il>1; 
                                   $<lp>$.nl = $<nl>2;
				   $<lp>$.iter = $<ival>3;}
	| comment inner iter       {$<lp>$.cmt = $<sval>1; 
				   $<lp>$.il = NULL; 
                                   $<lp>$.nl = $<nl>2;
				   $<lp>$.iter = $<ival>3;}
	| inner iter               {$<lp>$.cmt = NULL; 
				   $<lp>$.il = NULL; 
                                   $<lp>$.nl = $<nl>1;
				   $<lp>$.iter = $<ival>2;}
	| comment init iter        {$<lp>$.cmt = $<sval>1; 
				   $<lp>$.il = $<il>2; 
                                   $<lp>$.nl = NULL;
				   $<lp>$.iter = $<ival>3;}
	| init iter                {$<lp>$.cmt = NULL; 
				   $<lp>$.il = $<il>1; 
                                   $<lp>$.nl = NULL;
				   $<lp>$.iter = $<ival>2;}
	| comment init             {$<lp>$.cmt = $<sval>1; 
				   $<lp>$.il = $<il>2; 
                                   $<lp>$.nl = NULL;}
	| init                     {$<lp>$.cmt = NULL; 
				   $<lp>$.il = $<il>1; 
                                   $<lp>$.nl = NULL;}
;	

comment: BC commentbody EC {*$<sval>2='\0'; $<sval>$=strdup(cmtline);}
;

commentbody: /* empty */         {$<sval>$=cmtline;} 
	| commentbody CHR        {*$<sval>$=$<cval>2; $<sval>$++;}

;

init:     BI initbody EI         {$<il>$ = $<il>2; }
;

initbody: initline           {$<il>$=IInsert(NULL,$<ia>1);}
	| initbody initline  {$<il>$=IInsert($<il>1,$<ia>2);}
;

inner:     BN innerbody EN   {$<nl>$ = $<nl>2;}
;

innerbody: innerline             {$<nl>$=NInsert(NULL,$<na>1);}
	|  innerbody innerline   {$<nl>$=NInsert($<nl>1,$<na>2);}
;

iter:	   IT NUM            {$<ival>$ = $<ival>2;}
;

initline: ilbody DISAB       {$<ia>$ = $<ia>1; $<ia>$.block=FALSE; $<ia>$.en = FALSE;}
        | ilbody BR          {$<ia>$ = $<ia>1; $<ia>$.block=TRUE;  $<ia>$.en = TRUE;}
	| ilbody             {$<ia>$ = $<ia>1; $<ia>$.block=FALSE; $<ia>$.en = TRUE;}
;

ilbody:    ibinary           {$<ia>$ = $<ia>1;}
	|  ienum             {$<ia>$ = $<ia>1;}
	|  iscalar           {$<ia>$ = $<ia>1;}
	|  isimple	     {$<ia>$ = $<ia>1;}
	|  itest	     {$<ia>$ = $<ia>1;}
;

isimple: CODE                {$<ia>$.id=$<ival>1;
	                      $<ia>$.cval.fval=MAXDOUBLE;
	                      $<ia>$.cval.sval=NULL;}
;

ibinary: BIN CODE            {$<ia>$.id=$<ival>2;
	                      $<ia>$.cval.bval=$<ival>1;
	                      $<ia>$.cval.fval=MAXDOUBLE;
	                      $<ia>$.cval.sval=NULL;}
;

ienum: STATE CODE            {$<ia>$.id=$<ival>2;
	                      $<ia>$.cval.ival=$<ival>1;
	                      $<ia>$.cval.fval=MAXDOUBLE;
	                      $<ia>$.cval.sval=NULL;}
;

iscalar:  PARM CODE          {$<ia>$.cval.fval=$<fval>1;
			      $<ia>$.id=$<ival>2;
	                      $<ia>$.cval.sval=NULL;}
;

itest:  GFIB ADDR DATA CODE  {$<ia>$.cval.ival=$<ival>3;
	                      $<na>$.cval.fval=MAXDOUBLE;
			      $<ia>$.id=$<ival>4;
	                      $<ia>$.addr=$<ival>2;}
;


innerline:    nlbody DISAB   {$<na>$=$<na>1; $<na>$.block=FALSE; $<na>$.en=FALSE;}
           |  nlbody BR      {$<na>$=$<na>1; $<na>$.block=TRUE;  $<na>$.en=TRUE;}
	   |  nlbody         {$<na>$=$<na>1; $<na>$.block=FALSE; $<na>$.en=TRUE;}
; 

nlbody:   TIME nbinary       {$<na>$=$<na>2; $<na>$.time=$<lval>1;} 
	| TIME nenum         {$<na>$=$<na>2; $<na>$.time=$<lval>1;} 
	| TIME ramp          {$<na>$=$<na>2; $<na>$.time=$<lval>1;} 
 	| TIME nscalar       {$<na>$=$<na>2; $<na>$.time=$<lval>1;}  
        | TIME nsimple       {$<na>$=$<na>2; $<na>$.time=$<lval>1;} 
        | TIME ntest         {$<na>$=$<na>2; $<na>$.time=$<lval>1;} 
;

nsimple: CODE                {$<na>$.id=$<ival>1;
	                      $<na>$.ramp=FALSE;
			      $<na>$.ord=UINT_MAX;
			      $<na>$.cval.fval=MAXDOUBLE;
	                      $<na>$.cval.sval=NULL;}

;

nbinary: BIN CODE            {$<na>$.id=$<ival>2;
                              $<na>$.ramp=FALSE;
			      $<na>$.ord=UINT_MAX;
	                      $<na>$.cval.bval=$<ival>1;
	                      $<na>$.cval.fval=MAXDOUBLE;
	                      $<na>$.cval.sval=NULL;}
;

nenum: STATE CODE            {$<na>$.id=$<ival>2;
			      $<na>$.ramp=FALSE;
			      $<na>$.ord=UINT_MAX;      
	                      $<na>$.cval.fval=MAXDOUBLE;
                              $<na>$.cval.ival=$<ival>1;
	                      $<na>$.cval.sval=NULL;}
;


nscalar:  PARM CODE          {$<na>$.id=$<ival>2;
                              $<na>$.ramp=FALSE;
			      $<na>$.ord=UINT_MAX;
			      $<na>$.cval.fval=$<fval>1;
	                      $<na>$.cval.sval=NULL;}
;

ntest:  GFIB ADDR DATA CODE  {$<na>$.id=$<ival>4;
                              $<na>$.ramp=FALSE;
                              $<na>$.ord=UINT_MAX;
			      $<na>$.addr=$<ival>2;
			      $<na>$.cval.ival=$<ival>3;
	                      $<na>$.cval.fval=MAXDOUBLE;
                              $<na>$.cval.sval=NULL;}

	                      
;

ramp:  RMP PARM TIME STP CODE   {$<na>$.id=$<ival>5;
                                 $<na>$.ramp=$<ival>1;
			         $<na>$.ord=UINT_MAX;
				 $<na>$.fval=$<fval>2;
	                      	 $<na>$.cval.sval=NULL;
				 $<na>$.rt=$<lval>3;
				 $<na>$.steps=$<ival>4;}
      | RMP STATE TIME CODE     {$<na>$.id=$<ival>4;
                                 $<na>$.ramp=$<ival>1;
			         $<na>$.ord=UINT_MAX;
				 $<na>$.fval=$<ival>2;
				 $<na>$.cval.fval=MAXDOUBLE;
	                      	 $<na>$.cval.sval=NULL;
				 $<na>$.rt=$<lval>3;}
;

%%

int yyerror(char *er)
{
  return 0;		
}

