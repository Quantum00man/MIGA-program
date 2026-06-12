/* Format.c: */
/* M. Prevedelli (1998) */

#include <stdio.h>
#include <string.h>
#include "Types.h"
#include "DLList.h"
#include "Format.h"


#define linel 81
#define tab1 14
#define tab2 69
#define tab3 75
#define desl tab2-tab1

extern void Error();

void ASCIIFormat(char *fn, prog *pr)
{
  FILE *fp;
  initlist *il;  
  innerlist *nl;
  action *a;
  int l;
  char line[linel];
  char aux[linel];
  char aux2[linel];

if(pr)
  {
    if(!(fp=fopen(fn,"w")))
	Error("Could not open file");
    else
      {
	pr=PFirst(pr);
	do
	  {
	    fprintf(fp,"%s",BLOOP);
	    if (!(pr->lp.en))
	      fprintf(fp," %s",DISABLED);
	    fprintf(fp,"\n\n");
	    if(pr->lp.cmt)
	      {
		fprintf(fp,"%s\n",BCOMMENT);
		fprintf(fp,"%s",pr->lp.cmt);
		fprintf(fp,"%s\n\n",ENCOMMENT);
	      }
	    il=IFirst(pr->lp.il);
	    if(il)
	      {
		fprintf(fp,"%s\n",BINIT);
		do
		  {
		    a=&FunList[il->ia.id];
		    for(l=0;l<tab1;line[l++]=' ');
		    line[tab1]='\0';
		    switch(a->type)
		      {
		      case SIMPLE_A:
			strncat(line,a->ds,desl-1);		    
			break;
		      case BINARY_A:
			  sprintf(aux," = %s",(il->ia.cval.bval) ? BINON : BINOFF);
			  l=desl-strlen(aux);
			  strncat(line,a->ds,l);
			  strcat(line,aux);
			  break;
		      case ENUM_A:
			  sprintf(aux," [%d]",il->ia.cval.ival);
			  l=desl-strlen(aux);
			  strncat(line,a->ds,l);
			  strcat(line,aux);
			  break;
		      case SCALAR_A:
			  snprintf(aux2,linel,a->fm,il->ia.cval);
			  snprintf(aux,linel," = %s %s",aux2,a->un);
			  l=desl-strlen(aux);
			  strncat(line,a->ds,l);
			  strcat(line,aux);
			  break;
		      case TEST_A:
			  sprintf(aux,"[%d] = %d",il->ia.addr,il->ia.cval.ival);
			  l=desl-strlen(aux);
			  strncat(line,a->ds,l);
			  strcat(line,aux);
			  break;
		      }			
		    for(l=strlen(line);l<tab2;line[l++]=' ');
		    line[tab2]='\0';
		    sprintf(aux,"(%u)",a->id);
		    strcat(line,aux);
		    if(!(il->ia.en))
		      {
			for(l=strlen(line);l<tab3;line[l++]=' ');
			line[tab3]='\0';
			strcat(line,DISABLED);
		      }
		    if(il->ia.block)
		      {
			for(l=strlen(line);l<tab3;line[l++]=' ');
			line[tab3]='\0';
			strcat(line,BREAK);
		      }
		    fprintf(fp,"%s\n",line);
		  }
		while((il=il->next));
		fprintf(fp,"%s\n\n",ENINIT);
	      }
	    nl=NFirst(pr->lp.nl);
	    if(nl)
	      {
		fprintf(fp,"%s\n",BINNER);
		do
		  {
		    a=&FunList[nl->na.id];
		    for(l=0;l<tab1;line[l++]=' ');
		    sprintf(aux,"%llius",nl->na.time/1000LL);
		    l=tab1-strlen(aux)-1;
		    strcpy(line+l,aux);
		    for(l=strlen(line);l<tab1;line[l++]=' ');
		    line[tab1]='\0';
		    switch(a->type)
		      {
		      case SIMPLE_A:
			strncat(line,a->ds,desl-1);		    
			break;
		      case BINARY_A:
			sprintf(aux," = %s",(nl->na.cval.bval) ? BINON : BINOFF);
			l=desl-strlen(aux);
			strncat(line,a->ds,l);
			strcat(line,aux);
			break;
		      case ENUM_A:
			sprintf(aux," [%d]",nl->na.cval.ival);
			l=desl-strlen(aux);
			strncat(line,a->ds,l);
			strcat(line,aux);
			break;
		      case SCALAR_A:
			if(nl->na.ramp)
			  {
			    snprintf(aux2,linel,a->fm,nl->na.fval);
			    snprintf(aux,linel," %s %s %s %s %dus (%u %s)",TO,
				    aux2,a->un, IN, 
				    (int)(nl->na.rt/1000LL),  
				    nl->na.steps, STEPS);
			    l=desl-strlen(aux)-strlen(RAMP);
			    strcat(line,RAMP); 
			  }
			else
			  {
			    snprintf(aux2,linel,a->fm,nl->na.cval);
			    snprintf(aux,linel," = %s %s",aux2,a->un);
			    l=desl-strlen(aux);
			  }
			strncat(line,a->ds,l);
			strcat(line,aux);
			break;
		      case TEST_A:
			sprintf(aux,"[%d] = %d",nl->na.addr,nl->na.cval.ival);
			l=desl-strlen(aux);
			strncat(line,a->ds,l);
			strcat(line,aux);
			break;
		      }
		    for(l=strlen(line);l<tab2;line[l++]=' ');
		    line[tab2]='\0';
		    sprintf(aux,"(%u)",a->id);
		    strcat(line,aux);
		    if(!(nl->na.en))
		      {
			for(l=strlen(line);l<tab3;l++)
			  line[l]=' ';
			line[tab3]='\0';
			strcat(line,DISABLED);
		      }
		    if(nl->na.block)
		      {
			for(l=strlen(line);l<tab3;l++)
			  line[l]=' ';
			line[tab3]='\0';
			strcat(line,BREAK);
		      }
		    fprintf(fp,"%s\n",line);
		  }
		while((nl=nl->next));
		fprintf(fp,"%s\n\n",ENINNER);
	      }
	    fprintf(fp,"%s %u \n\n",ITER,pr->lp.iter);
	    fprintf(fp,"%s\n\n",ENLOOP);
	  }
	while((pr=pr->next));
	fclose(fp); 
      }
  }
}

int log2i(int n)
{
  int cnt=0;

  while(n)
    {
      n>>=1;
      cnt++;
    }

  return cnt;
}

void mkbin(char p[linel],int n,int sz)
{
  int i,j,k;

  i=log2i(sz);
  j=1<<(i-1);
  p[0]='b';
  for(k=1;k<i+1;k++)
    {
      if(n<0)
	p[k]='x';
      else
	{
	  p[k]=(n & j) ? '1' : '0';
	  j>>=1;
	}
    }
  p[k]='\0';
}

void VCDDump(char *fn, prog *pr)
{
  FILE *fp;
  initlist *il;  
  innerlist *nl;
  int i,j,k;
  int cnt=1;
  int cu[FUNLISTSIZE],adu[MAXADDR];
  char aux[linel];

if(pr)
  {
    if(!(fp=fopen(fn,"w")))
	Error("Could not open file");
    else
      {
	//per adesso solo il primo loop
	pr=PFirst(pr);
	if(pr)
	  {
	    fprintf(fp,"$timescale 1ns $end\n");
	    if (pr->lp.en)
	      {
		fprintf(fp,"$scope module loop%d $end\n",cnt);
		cnt++;	   
		for(i=0;i<FUNLISTSIZE;i++)
		  cu[i]=0;
		for(i=0;i<MAXADDR;i++)
		  adu[i]=0;
		il=IFirst(pr->lp.il);
		if(il)
		  {
		    do
		      if(il->ia.en)
                        {
			if(FunList[il->ia.id].type==TEST_A)
			  adu[il->ia.addr]=1;
			else
			  cu[il->ia.id]=1;
                        }
		    while((il=il->next));
		  }
		nl=NFirst(pr->lp.nl);
		if(nl)
		  {
		    do
		      if(nl->na.en)
                       {
			if(FunList[nl->na.id].type==TEST_A)
			  adu[nl->na.addr]=1;
			else
			  cu[nl->na.id]=1;
                       }
		    while((nl=nl->next));
		  }
		for(i=0;i<FUNLISTSIZE;i++)
		  if(cu[i])
		    {
		      strncpy(aux,FunList[i].ds,linel);
		      k=0;
		      while(aux[k]==' ')
			k++;
		      for(j=k;j<strlen(aux);j++)
			if(aux[j]==' ' || aux[j]=='.')
			  aux[j]='_';
		      switch(FunList[i].type)
			{
			case SIMPLE_A:
			  fprintf(fp,"$var wire 1 %d %s $end\n",i,aux);			  
			  break;
			case BINARY_A:
			  fprintf(fp,"$var reg 1 %d %s $end\n",i,aux);			  
			  break;
			case ENUM_A:
			  j=log2i(FunList[i].gfib.smax-1);
			  fprintf(fp,"$var reg %d %d %s [%d:0] $end\n",j,i,aux,j-1);			  
			  break;
			case SCALAR_A:
			  fprintf(fp,"$var real 64 %d %s $end\n",i,aux);			  
			}
		    
		    }
		for(i=0;i<MAXADDR;i++)
		  if(adu[i])
		    fprintf(fp,"$var reg 16 A%d ADDR_%d [15:0] $end\n",i,i);			  
		
		fprintf(fp,"$enddefinitions $end\n");			  
		fprintf(fp,"$dumpvars\n");			  
		il=IFirst(pr->lp.il);
		nl=NUnroll(pr->lp.nl);		
		if(il)
		  {
		    do
		      {
			i=il->ia.id;
			switch(FunList[i].type)
			  {
			  case SIMPLE_A:
			    cu[i]=2;
			    fprintf(fp,"1%d\n",i);
			    break;
			  case BINARY_A:
			    cu[i]=2;
			    fprintf(fp,"%d%d\n",il->ia.cval.bval,i);			  
			    break;
			  case ENUM_A:
			    cu[i]=2;
			    mkbin(aux,il->ia.cval.ival,FunList[i].gfib.smax-1);
			    fprintf(fp,"%s %d\n",aux,i);			  
			    break;
			  case SCALAR_A:
			    cu[i]=2;
			    fprintf(fp,"r%.16g %d\n",il->ia.cval.fval,i);			  
			    break;
			  case TEST_A:
			    adu[i]=2;
			    mkbin(aux,il->ia.cval.ival,65535);
			    fprintf(fp,"%s A%d\n",aux,il->ia.addr);			  
			    break;
			  }
		      }
		    while((il=il->next));
		    for(i=0;i<FUNLISTSIZE;i++)
		      if(cu[i]==1)
			{
			  switch(FunList[i].type)
			    {
			    case SIMPLE_A:
			    case BINARY_A:
			      fprintf(fp,"x%d\n",i);			  
			      break;
			    case ENUM_A:
			      mkbin(aux,-1,FunList[i].gfib.smax-1);
			      fprintf(fp,"%s %d\n",aux,i);			  
			      break;
			    }
			}

		    for(i=0;i<MAXADDR;i++)
		      if(adu[i]==1)
			{
			  mkbin(aux,-1,65535);
			  fprintf(fp,"%s A%d\n",aux,i);			  
			  break;
			}
		    fprintf(fp,"$end\n");	    
		  }
		fprintf(fp,"#%llu\n",CLOCKPERIOD);			  
		for(i=0;i<FUNLISTSIZE;i++)
		  if(cu[i]==2 && FunList[i].type==SIMPLE_A)
		    fprintf(fp,"0%d\n",i);			  
		nl=NFirst(nl);
		if(nl)
		  {
		    do
		      {
			if(nl->na.en)
			  {
			    if(!nl->na.ord)
			      fprintf(fp,"#%llu\n",nl->na.time);
			    i=nl->na.id;
			    switch(FunList[i].type)
			      {
			      case SIMPLE_A:
				fprintf(fp,"1%d\n",i);		
				fprintf(fp,"#%llu\n",nl->na.time+CLOCKPERIOD);
				fprintf(fp,"0%d\n",i);		
				fprintf(fp,"#%llu\n",nl->na.time);	  
				break;
			      case BINARY_A:
				fprintf(fp,"%d%d\n",nl->na.cval.bval,i);			  
				break;
			      case ENUM_A:
				mkbin(aux,nl->na.cval.ival,FunList[i].gfib.smax-1);
				fprintf(fp,"%s %d\n",aux,i);			  
				break;
			      case SCALAR_A:
				fprintf(fp,"r%0.16g %d\n",nl->na.cval.fval,i);	
				break;
			      case TEST_A:
				mkbin(aux,nl->na.cval.ival,65535);
				fprintf(fp,"%s A%d\n",aux,nl->na.addr);			  
			      }
			  }
		      }
		    while((nl=nl->next));
		    NClear(nl);
		  }
	      }
	  }	      
	fclose(fp); 
      }
  }
}



