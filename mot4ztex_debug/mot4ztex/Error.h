/* Error.h: Error Codes */
/* M. Prevedelli (1998) */ 

#ifndef _Error_
#define _Error_

#define DLLECODE  1      /* wrong code */
#define DLLETIME  2      /* Time too big */
#define DLLERANGE 3      /* param out of range */
#define DLLESHORT 4      /* step too short in ramp */
#define DLLERNSC  5      /* ramp with non scalar action */
#define DLLELOOP  6      /* invalid loop */
#define DLLEROVL  7      /* two ramps overlap */
#define DLLERSOVL 8      /* ramp and scalar action overlap */
#define DLLERTLG  9      /* ramp too long */
#define DLLERLOG  10     /* range error in LOG ramp */
#define DLLEGADDR 11     /* GFIB Address out of range */
#define MEMESIZE  12     /* out of memory */
#define NOTAPROG  13     /* Not a program file */
#define DLLEZINT  14     /* Zero Inner first time */
#define DLLESAMET 15     /* two actions at same time */


#endif /* _Error_ */











































