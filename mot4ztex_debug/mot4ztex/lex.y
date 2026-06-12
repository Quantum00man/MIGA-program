/* scanner for MOT2 */
/* M. Prevedelli 1998 */

%{
#include <strings.h>
#include <ctype.h>
#include "Types.h"
#include "parser.tab.h"
#include "stdlib.h"

long long ctime;
int caller;	
%}

%option noyywrap

%x LOOP
%x COMMENT
%x INIT
%x INNER
%x RAMP
%x TEST

INT [0-9]+
HEXNUM ("0x"[0-9a-fA-F]+)|{INT}
CODE "("" "*{INT}" "*")"
STATE "["" "*{INT}" "*"]"
FLOAT ([0-9]+"."?[0-9]*)|("."[0-9]+)
RFLOAT "+"?{FLOAT}
SFLOAT ("+"?)|("-"?){FLOAT}
RTIME {RFLOAT}" "?[nNuUmM]?[sS]
TIME {FLOAT}" "?[nNuUmM]?[sS]
ON  "="" "*[oO][nN]
OFF "="" "*[oO][fF][fF]
GFIB [gG][fF][iI][bB]
LINECMT ^"#"
%%

LOOP[ \t\r\n]            {BEGIN(LOOP); return BL;}
.|\n                     /* ignore all the rest */ 

<LOOP>{LINECMT}.*|\n   /* ignore */

<LOOP>IDLE[ \t\r\n]      {return DISAB;}   

<LOOP>COMMENT[ \t\r\n]   {BEGIN(COMMENT); return BC;}   

<LOOP>INIT[ \t\r\n]      {BEGIN(INIT); return BI;}   

<LOOP>INNER[ \t\r\n]     {BEGIN(INNER); ctime=0; return BN;}   

<LOOP>ITERATIONS[ \t\r\n] {return IT;}   

<LOOP>{INT}              {yylval.ival=(unsigned)strtol(yytext,NULL,10); 
                          return NUM;}   

<LOOP>ENDLOOP[ \t\r\n]*    {BEGIN(0); return EL;}   

<LOOP>.|\n               /* ignore all the rest */ 

<COMMENT>ENDCOMMENT[ \t\r\n]    {BEGIN(LOOP); return EC;}   

<COMMENT>.|\n	                {yylval.cval=*yytext; return CHR;}

<INIT,INNER>{LINECMT}.*|\n   /* ignore */

<INIT,INNER>{CODE}        {yylval.ival=strtol(yytext+1,NULL,10); 
			   return CODE;}

<INIT,INNER>{ON}        {yylval.bval=1; 
			 return BIN;}

<INIT,INNER>{OFF}       {yylval.bval=0; 
			 return BIN;}

<INIT,INNER>{STATE}     {yylval.ival=strtol(yytext+1,NULL,10);  
			 return STATE;}

<INIT>{GFIB}            {BEGIN(TEST); caller=INIT;
                         return GFIB;}  

<INNER>{GFIB}           {BEGIN(TEST); caller=INNER;
                         return GFIB;}  

<INIT,INNER>LINECMT   

<INIT,INNER>IDLE[ \t\r\n]  {return DISAB;}   

<INIT,INNER>BREAK[ \t\r\n] {return BR;}   

<INIT>ENDINIT[ \t\r\n]     {BEGIN(LOOP); return EI;}

<INIT>.|\n               /* ignore all the rest */ 

<INNER>RAMP[ \t]*         {BEGIN(RAMP); caller=INNER; 
                           yylval.ival=RAMPLIN;
                           return RMP;}

<INNER>RAMPLOG[ \t]*       {BEGIN(RAMP); caller=INNER; 
                            yylval.ival=RAMPLOG;
                            return RMP;}

<INIT,INNER>=" "*{SFLOAT} {yylval.fval=strtod(yytext+1,NULL); 
			    return PARM;}

<INNER>{RTIME}            {double a; char *p;
                           a=strtod(yytext,&p);
			   if(*p==' ')
			     p++;
			   switch(*p)
                            {
			     case 'n':
                             case 'N':
                               break; 
                             case 'u':
                             case 'U':
			       a *= 1000;
                               break; 
			     case 'm':
                             case 'M':
			       a *= 1000000;
                               break;
                             case 's':
                             case 'S':
			       a *= 1000000000;
                               break; 
			     default:
			       a *= 1000;
                            }
			   if(yytext[0]=='+')
			      a += ctime;
                           yylval.lval = a > MAXNS ? MAXNS+1 : a;
                           ctime=yylval.lval;
                           return TIME;}

<INNER>ENDINNER[ \t\r\n] {BEGIN(LOOP); return EN;}

<INNER>.|\n              /* ignore all the rest */ 

<RAMP>TO" "*{SFLOAT}      {yylval.fval=strtod(yytext+2,NULL); 
			  return PARM;}

<RAMP>{TIME} {double a; char *p;
                          a=strtod(yytext,&p);
			  if(*p==' ')
			    p++;
			  switch(*p)
                           {
			    case 'n':
                            case 'N':
                              break; 
                            case 'u':
                            case 'U':
			      a *= 1000;
                              break; 
			    case 'm':
                            case 'M':
			      a *= 1000000;
                              break;
                            case 's':
                            case 'S':
			      a *= 1000000000;
                              break; 
			    default:
			      a *= 1000;
                           }
                          yylval.lval = a > MAXNS ? MAXNS+1 : a;
                          return TIME; }

<RAMP>{INT}" "*STEPS     {yylval.ival=strtol(yytext,NULL,10);
                          return STP; }

<RAMP>{CODE} {yylval.ival=strtol(yytext+1,NULL,10); 
	      BEGIN(caller); return CODE;}


<RAMP>TO" "*{STATE}      {char *p;
                          p=yytext+2;
                          while(*p!='[')
			    p++;
			  p++;
                          yylval.ival=strtol(p,NULL,10); 
			  return STATE;}

<TEST>{STATE}       {yylval.ival=strtol(yytext+1,NULL,10);
                     return ADDR;}

<TEST>=" "*{HEXNUM} {yylval.ival=strtol(yytext+1,NULL,0);
                     return DATA;}

<TEST>{CODE} {yylval.ival=strtol(yytext+1,NULL,10);
              BEGIN(caller); return CODE;}
%%
