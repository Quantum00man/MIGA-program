/* DLList.c: */
/* M. Prevedelli (1998) */

#include "DLList.h"
#include <stdio.h>
#include <malloc.h>
#include <limits.h>
#include <values.h>
#include <math.h>


int ICheck(initact ia)
{
  if(!ia.en)
    return 0;
  if(FunList[ia.id].id != ia.id)
    return DLLECODE;
  if(FunList[ia.id].type & TEST_A)
    {
      if(ia.cval.ival>0xffff || ia.cval.ival<0)
	return DLLERANGE;
      if(ia.addr>MAXADDR || ia.addr<MINADDR)
	return DLLERANGE;
    }
  if(FunList[ia.id].type & ENUM_A)
    {
      if(ia.cval.ival>=FunList[ia.id].gfib.smax || ia.cval.ival<0)
	return DLLERANGE;
    }
  if(FunList[ia.id].type & SCALAR_A)
    {
      if((ia.cval.fval < FunList[ia.id].min) || 
	 (ia.cval.fval > FunList[ia.id].max))
	return DLLERANGE; 
    }
  else
    if(ia.cval.fval != MAXDOUBLE)
      return DLLECODE;
  return 0; 
}

initlist* IFirst(initlist* il)
{
  if(il)
    {
      while(il->prev)
	il=il->prev;
      return il;
    }
  else
    return NULL;
}

initlist* ILast(initlist* il)
{
  if(il)
    {
      while(il->next)
	il=il->next;
      return il;
    }
  else
    return NULL;
}

initlist* IDelete(initlist *il)
{
  initlist *p,*n;

  if(il)
    {
      p=il->prev;
      n=il->next;

      if(p)
	p->next=n;
      if(n)
	n->prev=p;
      if(!il->ia.cval.sval)
	free(il->ia.cval.sval);
      free(il);
      if(p)
	return p;
      if(n)
	return n;
    }
  return NULL;
}

initlist* IInsert(initlist *il, initact ia)
{
  initlist *p, *q;
  action *al;

  p=(initlist *)malloc(sizeof(initlist));
  p->ia=ia;

  for(q=IFirst(il);q;q=q->next)
    {
      al=&FunList[q->ia.id];
      if((al->type == TEST_A && q->ia.addr == ia.addr) || 
	 ((al->type != TEST_A) && (al->fam == FunList[p->ia.id].fam)))
	{
	  il=IDelete(q);
	  break;
	}
    }

  if(FunList[ia.id].type == SCALAR_A)
    FunList[ia.id].cval.fval = ia.cval.fval;
  if(FunList[ia.id].type == BINARY_A || FunList[ia.id].type == ENUM_A)
    FunList[ia.id].cval.bval = ia.cval.bval;
  if(il)
    {
      q=il->next;
      il->next=p;
      p->prev=il;
      p->next=q;
    }
  else
    {
      p->prev=NULL;
      p->next=NULL;
    }
  return p;
}

initlist* ICopy(initlist *il)
{
  initlist *p, *q;
  
  p=NULL;
  if(il)
    for(q=IFirst(il);q;q=q->next)
      p=IInsert(p,q->ia);
  return p;
}

initlist* IClear(initlist* il)
{

  while(il)
    il=IDelete(il);
  return NULL;
}

int NChkTime(innerlist* nl, long long t)
{
  int i=0;

  if(nl)
    {
      nl=NFirst(nl);
      while(nl)
	{
	  if(nl->na.time==t)
	    i++;
	  nl=nl->next;
	}
    }
  return i;
}

int NCheck(innerlist* nl, inneract na)
{
  innerlist *q;
  long long ti1, ti2, te1, te2;
  int i=0,j=0;

  if(!na.en)
    return 0;
  if(FunList[na.id].id != na.id)
    return DLLECODE;
  if(na.time>MAXNS)
    return DLLETIME;
  if(na.time==0)
    return DLLEZINT;
  q=NFirst(nl);
  i=j=0;
  while(q)
    {
      if(q->na.time==na.time)
	{
	  if(q->na.id==na.id)
	    i++;
	  if(FunList[q->na.id].fam!=FunList[na.id].fam)
	    j++;
	}
      q=q->next;
    }
  if(i>1 || j)
    return DLLESAMET;
  if((na.ramp) && !(FunList[na.id].type & (SCALAR_A | ENUM_A)))
    return DLLERNSC;
  if(FunList[na.id].type & TEST_A)
    {
      if(na.cval.ival>0xffff || na.cval.ival<0)
	return DLLERANGE;
      if(na.addr>MAXADDR || na.addr<MINADDR)
	return DLLERANGE;
    }
  if(FunList[na.id].type & ENUM_A)
    {
      if(na.cval.ival<0 || na.cval.ival>=FunList[na.id].gfib.smax)
	return DLLERANGE;
    }
  if(FunList[na.id].type & SCALAR_A)
    {
      ti1=na.time;
      if(na.ramp)
	{
	  if((na.fval<FunList[na.id].min) || (na.fval>FunList[na.id].max))
	    return DLLERANGE;
	  if((na.ramp==RAMPLOG) && (na.cval.fval*na.fval)<=0)
	    return DLLERLOG; 
	  if((na.rt/na.steps)<MINDELAY)
	    return DLLESHORT;
	  te1=ti1+na.rt;
	  if (te1>MAXNS)
	    return DLLERTLG;
	  for(q=NFirst(nl);q;q=q->next)
	    if((q->na.id==na.id) && (q->na.time != na.time) 
	       && (q->na.ord != na.ord) && (q->na.en))
	      {
		ti2=q->na.time;
		if(q->na.ramp)
		  {
		    te2=ti2+q->na.rt;
		    if((te2>=ti1) && (ti2<=te1))
		      return DLLEROVL;
		  }
		else
		  if((ti1<=ti2) && (ti2<=te1)) 
		    return DLLERSOVL;
	      }
	}
      else
	{
	  if((na.cval.fval<FunList[na.id].min) || 
	     (na.cval.fval>FunList[na.id].max))
	    return DLLERANGE;
	  for(q=NFirst(nl);q;q=q->next)
	    if(q->na.id==na.id && q->na.en)
	      {
		ti2=q->na.time;
		if(q->na.ramp)
		  {
		    te2=ti2+q->na.rt;
		    if((ti1>=ti2) && (ti1<=te2))
		      return DLLEROVL;
		  }
	      }
	} 
    }
  else
    {
      if(na.cval.fval != MAXDOUBLE)
	return DLLECODE;
    }
  return 0;
}

innerlist* NFirst(innerlist* nl)
{
  if(nl)
    {
      while(nl->prev)
	nl=nl->prev;
      return nl;
    }
  else
    return NULL;
}

innerlist* NLast(innerlist* nl)
{ 
  if(nl)
    {
      while(nl->next)
	nl=nl->next;
      return nl;
    }
  else
    return NULL;
}

innerlist* NDelete(innerlist *nl)
{
  innerlist *p,*n;

  if(nl)
    {
      p=nl->prev;
      n=nl->next;
      
      if(p)
	p->next=n;
      if(n)
	n->prev=p;
      if(!nl->na.cval.sval)
	free(nl->na.cval.sval);
      free(nl);
      if(p)
	return p;
      if(n)
	return n;
    }
  return NULL;
}

innerlist* NInsList(innerlist *p1, innerlist *p2)
{
  innerlist *n, *h, *t;

  if(!p1)
    return p2;
  if(!p2) 
    return p1;
  n=p1->next;
  h=NFirst(p2);
  t=NLast(p2);
  p1->next=h;
  h->prev=p1;
  t->next=n;
  if(n)
    n->prev=t;
  return h;
}


innerlist* NInsert(innerlist *nl, inneract na)
{
  innerlist *p, *q;

  p=(innerlist *)malloc(sizeof(innerlist));
  p->na=na;
  p->next=NULL;
  p->prev=NULL;
  q=NFirst(nl);
  if(FunList[na.id].type == SCALAR_A)
    FunList[na.id].cval.fval = na.cval.fval;
  if((FunList[na.id].type == BINARY_A || FunList[na.id].type == ENUM_A) && !na.ramp)
    FunList[na.id].cval.ival = na.cval.ival;
  if(q)
    {
      while((q->next) && (q->next->na.time < p->na.time))
	q=q->next;
      while((q->next) && (q->next->na.time == p->na.time) && 
	    (q->next->na.ord < p->na.ord))
	q=q->next;
      if((q->na.time < p->na.time) || 
	 ((q->na.time == p->na.time) && (q->na.ord < p->na.ord)))
	p=NInsList(q,p);
      else
	{
	  if(q->prev)
	    p=NInsList(q->prev,p);
	  else
	    p=NInsList(p,q);
	}
      if(q->na.time != p->na.time)
	p->na.ord=0;
      else
	{
	  q=p;
	  while((q->prev) && (q->prev->na.time == q->na.time))
	    q=q->prev;
	  q->na.ord=0;
	  while((q->next) && (q->next->na.time == q->na.time))
	    {
	      q->next->na.ord=q->na.ord+1;
	      q=q->next;
	    }
	}
      return p;
    }
  else
    {
      p->na.ord=0;
      return NInsList(q,p);           
    }
}

innerlist* NCopy(innerlist *nl)
{
  innerlist *p, *q;

  p=NULL;
  if(nl)
    for(q=NFirst(nl);q;q=q->next)
      p=NInsert(p,q->na);
  return p;
}


innerlist* NUnroll(innerlist* nl)
{
  innerlist *p, *q;
  inneract au;
  int i,j,k;
  double cval, rs, or;

  p=NULL;
  if(nl)
    {
      p=(innerlist *)malloc(sizeof(innerlist));
      p->prev=NULL;
      p->next=NULL;
      p->na.time=MAXNS;
      p->na.ord=UINT_MAX;
      for(q=NFirst(nl);q;q=q->next)
	{
	  if(q->na.en)
	    {
	      if(q->na.ramp)
		{	  
		  if(FunList[q->na.id].type == ENUM_A)
		    {
		      au=q->na;
		      k=FunList[q->na.id].cval.ival;
		      rs=q->na.rt/fabs(q->na.fval-k);
		      j=(q->na.cval.ival>k) ? -1 : 1;
		      
		      for(i=k+1;i<q->na.fval;i+=j)
			{
			  au.time+=rs;
			  au.ord=UINT_MAX;
			  au.cval.ival=i;
			  NInsert(p,au);
			}
		      //adjust the last step
		      au.time=q->na.time+q->na.rt;
		      au.ord=UINT_MAX;
		      au.cval.ival=q->na.fval;
		      NInsert(p,au);
		    }
		  else
		    {
		      cval=FunList[q->na.id].cval.fval;
		      au=q->na;
		      switch(q->na.ramp)
			{
			case RAMPLOG:
			  rs=exp(log(au.fval/cval)/(double)q->na.steps);
			  break;
			case RAMPLIN:
			default:
			  rs=(au.fval-cval)/(double)q->na.steps;
			}
		      or=cval;
		      for(i=1;i<q->na.steps+1;i++)
			{
			  au.ramp=FALSE;
			  switch(q->na.ramp)
			    {
			    case RAMPLOG:
			      or*=rs;
			      break;
			    case RAMPLIN:
			    default:
			      or+=rs;
			    }
			  FunList[q->na.id].cval.fval=au.cval.fval=or;
			  au.time=q->na.time+i/(double)q->na.steps*q->na.rt;
			  au.ord=UINT_MAX;
			  NInsert(p,au);
			}
		      FunList[q->na.id].cval.fval=q->na.fval;
		    }
		}
	      else
		{
		  FunList[q->na.id].cval.fval=q->na.cval.fval;
		  NInsert(p,q->na);
		}
	    }
	}
      p=NDelete(NLast(p));
    }
  return p;
}

innerlist* NClear(innerlist* nl)
{
  while(nl)
    nl=NDelete(nl);
  return NULL;
}

int PCheck(loop lp)
{
  if(!lp.en)
    return 0;
  if(!(lp.il) && !(lp.nl))
    return DLLELOOP;
  else
    return 0;
}

prog* PFirst(prog* pr)
{ 
  if(pr)
    {
      while(pr->prev)
	pr=pr->prev;
      return pr;
    }
  else
    return NULL;
}

prog* PLast(prog* pr)
{ 
  if(pr)
    {
      while(pr->next)
	pr=pr->next;
      return pr;
    }
  else
    return NULL;
}

prog* PDelete(prog *pr)
{
  prog *p,*n;

  if(pr)
    {
      p=pr->prev;
      n=pr->next;
    
      if(p)
	p->next=n;
      if(n)
	n->prev=p;
      IClear(pr->lp.il);
      NClear(pr->lp.nl);
      free(pr);
      if(p)
	return p;
      if(n)
	return n;
    }
  return NULL;
}

prog* PInsert(prog *pr, loop lp)
{
  prog *p, *q;

  p=(prog *)malloc(sizeof(prog));
  p->lp=lp;
  if(pr)
    {
      q=pr->next;
      pr->next=p;
      p->prev=pr;
      p->next=q;
    }
  else
    {
      p->prev=NULL;
      p->next=NULL;
    }
  return p;
}


prog* PCopy(prog *pr, int *er)
{
  prog *p, *q;
  initlist *il;
  innerlist *nl;
  loop lp;

  p=NULL;
  if(!pr)
    return p;

  for(q=PFirst(pr);q;q=q->next)
    {
      if(q->lp.en)
	{
	  *er=PCheck(q->lp);
	  if(!(*er))
	    for(il=IFirst(q->lp.il);il;il=il->next)
	      {
		*er=ICheck(il->ia);
		if(*er)
		  break;
	      }
	  if(!(*er))
	    for(nl=NFirst(q->lp.nl);nl;nl=nl->next)
	      {
		*er=NCheck(q->lp.nl,nl->na);
		if(*er)
		  break;
	      }
	  if(*er)
	    break;
	  lp=q->lp;
	  lp.il=ICopy(q->lp.il);
	  lp.nl=NCopy(q->lp.nl);
	  p=PInsert(p,lp);
	}
    
    }
  return p;
}

prog* PInsList(prog *p1, prog *p2)
{
  prog *n, *h, *t;

  if(!p1)
    return p2;
  if(!p2) 
    return p1;
  n=p1->next;
  h=PFirst(p2);
  t=PLast(p2);
  p1->next=h;
  h->prev=p1;
  t->next=n;
  if(n)
    n->prev=t;
  return h;
}

prog* PClear(prog* pr)
{
  while(pr)
    pr=PDelete(pr);
  return NULL;
}











