/* Compile.c: */
/* M. Prevedelli (2009)*/

#include <limits.h>
#include <malloc.h>
#include <math.h>
#include <string.h>
#include "Types.h"
#include "DLList.h"
#include "Functions.h"

unsigned long long tmax;
unsigned long long waitmax;

#define CTime(X) (unsigned)(X/CLOCKPERIOD)

void cmdldinit(cmdload *cl)
{
  cl->addr=0;
  cl->data=0;
}

void cmdldsetaddr(cmdload *cl, unsigned addr)
{
  cl->addr=addr;
}

void cmdldsetcnt(cmdload *cl, unsigned long long d)
{
  cl->data&=0xf000000000ffffffULL;
  cl->data|=(d & 0xfffffffffULL)<<24;
}

void cmdldsetout(cmdload *cl, int addr, int data)
{
  cl->data&=0xffffffffff000000ULL;
  cl->data|=(addr & 0x7f)<<1;
  cl->data|=(data & 0xffff)<<8;
}

void InsertInit(int idx,initlist *ip)
{
  unsigned long long ct;
  unsigned addr;

  ct=CTime(INITDELAY);
  cmdldinit(cmdlist+idx);
  cmdldsetaddr(cmdlist+idx,idx);
  cmdldsetcnt(cmdlist+idx,ct);
  if(ip->ia.block)
    (cmdlist+idx)->data|=OP_BREAK;
  addr=(FunList[ip->ia.id].type == TEST_A) ? ip->ia.addr : FunList[ip->ia.id].gfib.addr;
  GFIBcs[addr] &= ~FunList[ip->ia.id].gfib.mask;
  GFIBcs[addr] |= FunList[ip->ia.id].compile(ip->ia.cval);
  cmdldsetout(cmdlist+idx,addr,GFIBcs[addr]);
}

void InsertInner(int idx,innerlist *np, long long t)
{
  unsigned long long ct;
  unsigned addr;
  int i,j;  
 
  ct=(t>MINDELAY) ? CTime(t) : CTime(MINDELAY);
  cmdldinit(cmdlist+idx);
  cmdldsetaddr(cmdlist+idx,idx);
  cmdldsetcnt(cmdlist+idx,ct);
  addr=(FunList[np->na.id].type == TEST_A) ? np->na.addr : FunList[np->na.id].gfib.addr;
  i=NChkTime(np,np->na.time);
  for(j=0;j<i;j++,np=np->next)
    {
      if(np->na.block)
	(cmdlist+idx)->data|=OP_BREAK;  
      GFIBcs[addr] &= ~FunList[np->na.id].gfib.mask;
      GFIBcs[addr] |= FunList[np->na.id].compile(np->na.cval);
    }
  cmdldsetout(cmdlist+idx,addr,GFIBcs[addr]); 
}

int LCompile(int idx,loop lp)
{
  initlist *ip;
  innerlist *np;
  unsigned jmp;
  long long t;
  unsigned long long ct;
  int i,j,d;

  ip=IFirst(lp.il);
  ct=CTime(INITDELAY);
  while(ip)
    {  
      if(ip->ia.en)
	{
	  InsertInit(idx,ip);
	  idx++;
	  if(idx==MAXNACT)
	    return -1;
	}
      ip=ip->next;
    }

  jmp=idx;
  np=NFirst(NUnroll(lp.nl));
  while(np)
    {
      if(np==NFirst(np))
	t=np->na.time;
      else
	t=np->na.time-np->prev->na.time;	    
      //insert dummies
      while(t>MAXDUMMYTIME)
	{
	  ct=CTime(MAXDUMMYTIME);
	  cmdldinit(cmdlist+idx);
	  cmdldsetaddr(cmdlist+idx,idx);
	  cmdldsetcnt(cmdlist+idx,ct);
	  (cmdlist+idx)->data|=OP_NOP;
	  cmdldsetout(cmdlist+idx,0,0);
	  idx++;
	  if(idx==MAXNACT)
	    return -1;
	  t-=MAXDUMMYTIME;
	}
      InsertInner(idx,np,t);
      idx++;
      if(idx==MAXNACT)
	return -1;
      do
	np=np->next;
      while(np && np->na.ord);
    }
  //unroll
  if(lp.iter>1)
    {
      d=(idx-jmp);
      if(idx+d*(lp.iter-1)>MAXNACT-2)
	return -1;
      for(i=0;i<lp.iter-1;i++)
	for(j=jmp;j<jmp+d;j++)
	  {
	    memcpy(cmdlist+idx,cmdlist+j,sizeof(cmdload));
	    cmdldsetaddr(cmdlist+idx,idx);
	    idx++;
	  }
    }
    
  NClear(np);
  return idx;
}

int Compile(prog *pr)
{
  prog  *p;
  int idx=0;

#ifdef DEBUG
  int i;
#endif
  
  if(pr)
    {
      p=PFirst(pr);
      while(p)
	{
	  if(p->lp.en)
	    {
	      idx=LCompile(idx,p->lp);
	      if(idx<0)
		return idx;
	    }
	  p=p->next;
	}
      //end
      cmdlist[idx-1].data|=OP_END;
#ifdef DEBUG
      for(i=0;i<idx;i++)
	printf("Instr %d: ctrl=%d time=%d addr=%d data=%d\n",cmdlist[i].addr, (cmdlist[i].data>>60 & 0xf),(cmdlist[i].data>>24 & 0xfffffffffULL),
	       (cmdlist[i].data>>1 & 0x7fULL),(cmdlist[i].data>>8 & 0xffffULL));
#endif      
      return (idx==MAXNACT) ? -1 : idx;
    }
  else
    return 0;
}
