/* Functions.h: Function codes */
/* M. Prevedelli (2009) */ 

#include "Types.h"

#ifndef _Functions_
#define _Functions_

#define iTest    (FUNLISTSIZE-1)
#define fTest    (FUNLISTSIZE-1)

/* id codes: must be less than FUNLISTSIZE */

/* DDS #1 - addr GFIB #2 */
#define iDDS1State     		1
#define iDDS1SelfState     	2
#define iDDS1RampCh0		3
#define iDDS1RampCh1		4
#define iDDS1RampCh0Ch1		5
#define iDDS1Trig     		6
 
/* DDS #4 - addr GFIB #6 */
#define iDDS4State     		7
#define iDDS4SelfState     	8
#define iDDS4RampCh0		9
#define iDDS4RampCh1	       10
#define iDDS4RampCh0Ch1	       11
#define iDDS4Trig     	       12

/* DDS #5 - addr GFIB #7 */
#define iDDS5State     	       13
#define iDDS5SelfState         14
#define iDDS5RampCh0	       15
#define iDDS5RampCh1	       16
#define iDDS5RampCh0Ch1	       17
#define iDDS5Trig     	       18

//DAC8#1 (GFIB #64-71)
#define iAOM_3DMOT_Down		20
#define iAOM_3DMOT_Up		21
#define iAOM_Det		22
#define iAOM_Raman1		23
#define iAOM_Raman2		24
#define iBRD1DAC5SelfState	25
#define iVCA_3DMOT_Down		26
#define iVCA_3DMOT_Up		27

//DAC8#2 (GFIB #72-79)
#define iBRD2DAC0SelfState     	30
#define iBias_X			31
#define iBRD2DAC2SelfState     	32
#define iBias_Y     		33
#define iBRD2DAC4SelfState     	34
#define iBias_Z    		35
#define iBRD2DAC6SelfState     	36
#define iBRD2DAC7SelfState     	37


//DIGITAL OUTPUT (GFIB #1)
#define iRaman_Dw_Shutter      	40
#define iRaman_Up_Shutter     	41
#define iRepump_MOT_Shutter    	42
#define iRepump_Push_Shutter   	43
#define iRepump_Det_Shutter    	44
#define iDetection_Shutter     	45
#define i3DMOT_Up_Shutter     	46
#define i3DMOT_Down_Shutter	47
#define i2DMOT_Shutter         	48
#define iAOM_Raman1_Switch	49
#define iAOM_Raman2_Switch	50
#define iAOM_3DMOT_Up_Switch	51
#define iAOM_Det_Switch		52
#define iAOM_3DMOT_Down_Switch	53
#define iTTL1D14		54
#define iTTL1D15		55

//DIGITAL OUTPUT (GFIB #5)
#define iExp_Trig		60
#define iTTL2D1			61
#define iTTL2D2			62
#define iBragg_up		63
#define iBragg_Down		64
#define iBias_Coils		65
#define iBias_Bars		66
#define i3DMOT_Coils		67
#define iRedpitaya_Top		68
#define iTTL2D9		        69
#define iTTL2D10		70
#define iTTL2D11		71
#define iTTL2D12               	72
#define iTTL2D13               	73
#define iTTL2D14               	74
#define iTTL2D15               	75


/* families: must be less than FUNLISTSIZE */

#define fDDS1State		1
#define fDDS1SelfState		2
#define fDDS1Ramp		3
#define fDDS1Trig	        4

#define fDDS4State		5
#define fDDS4SelfState		6
#define fDDS4Ramp		7
#define fDDS4Trig	        8

#define fDDS5State		9
#define fDDS5SelfState	       10
#define fDDS5Ramp	       11
#define fDDS5Trig	       12

#define fBRD1DAC0SelfState     20
#define fBRD1DAC1SelfState     21
#define fBRD1DAC2SelfState     22
#define fBRD1DAC3SelfState     23
#define fBRD1DAC4SelfState     24
#define fBRD1DAC5SelfState     25
#define fBRD1DAC6SelfState     26
#define fBRD1DAC7SelfState     27

#define fBRD2DAC0SelfState     30
#define fBRD2DAC1SelfState     31
#define fBRD2DAC2SelfState     32
#define fBRD2DAC3SelfState     33
#define fBRD2DAC4SelfState     34
#define fBRD2DAC5SelfState     35
#define fBRD2DAC6SelfState     36
#define fBRD2DAC7SelfState     37

#define fTTL1D 	               40

#define fTTL2D 	               50

#endif /* _Functions_ */













