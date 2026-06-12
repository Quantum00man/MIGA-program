/* Format.h: constants for program files */
/* M. Prevedelli (1998) */ 
#ifndef _Format_
#define _Format_

#include "Types.h"

#define BLOOP "LOOP"
#define ENLOOP "ENDLOOP"

#define BCOMMENT "COMMENT"
#define ENCOMMENT "ENDCOMMENT"

#define BINIT "INIT"
#define ENINIT "ENDINIT"

#define BINNER "INNER"
#define ENINNER "ENDINNER"

#define ITER "ITERATIONS"
#define DISABLED "IDLE"
#define RAMP "RAMP "
#define TO "TO"
#define IN "IN"
#define STEPS  "STEPS"
#define BREAK  "BREAK"
#define BINON  "On"
#define BINOFF "Off"


void ASCIIFormat(char *fn, prog *pr);
void VCDDump(char *fn, prog *pr);

#endif /* _Format_ */











































