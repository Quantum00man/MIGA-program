/* DLList.h: Double Linked Lists functions */
/* M. Prevedelli (1998) */ 

#ifndef _DLList_
#define _DLList_

#include "Types.h"
#include "Error.h"

int ICheck(initact ia);
initlist* IFirst(initlist* il);
initlist* ILast(initlist* il);
initlist* IDelete(initlist* il);
initlist* IInsert(initlist* il, initact ia);
initlist* ICopy(initlist* il);
initlist* IClear(initlist* il);

int NCheck(innerlist* nl, inneract na);
innerlist* NFirst(innerlist* nl);
innerlist* NLast(innerlist* nl);
innerlist* NDelete(innerlist* nl);
innerlist* NInsList(innerlist *p1, innerlist *p2);
innerlist* NInsert(innerlist *nl, inneract na);
innerlist* NCopy(innerlist *nl);
int NChkTime(innerlist* nl, long long t);
innerlist* NUnroll(innerlist* nl);
innerlist* NClear(innerlist* nl);

int PCheck(loop lp);
prog* PFirst(prog* pr);
prog* PLast(prog* pr);
prog* PDelete(prog* pr);
prog* PInsert(prog *pr, loop lp);
prog* PCopy(prog *pr, int *er);
prog* PInsList(prog *p1, prog *p2);
prog* PClear(prog* pr);

#endif /* _DLList_ */











































