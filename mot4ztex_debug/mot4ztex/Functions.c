/* Functions.c: */
/* M. Prevedelli (2009) */

#include "Types.h"
#include "Functions.h"
#include <stdio.h>
#include <string.h>
#include <math.h>

action FunList[FUNLISTSIZE];
unsigned GFIBcs[ADDRSPACE];

unsigned cTest(val v)
{
  return v.ival & 0xffff;
}

unsigned cAD9958state(val v)
{
  return ((v.ival & 0x3ff) | 0x4000);
}

unsigned cAD9958selfstate(val v)
{
  return (cAD9958state(v) | 0x0400);
}

unsigned cAD9958dxstate(val v)
{
  return ((v.ival & 0x3ff) | 0x4000);
}

unsigned cAD9958dxselfstate(val v)
{
  return (cAD9958dxstate(v) | 0x0200);
}

unsigned cAD9958dxRampCh0(val v)
{
  return v.bval ? 0x1000 : 0;
}

unsigned cAD9958dxRampCh1(val v)
{
  return v.bval ? 0x2000 : 0;
}

unsigned cAD9958dxRampCh0Ch1(val v)
{
  return v.bval ? 0x3000 : 0;
}

unsigned cAD9959state(val v)
{
  return ((v.ival & 0x1ff) | 0x4000);
}

unsigned cAD9959selfstate(val v)
{
  return (cAD9959state(v) | 0x0200);
}

unsigned cAD9854state(val v)
{
  return ((v.ival & 0x1ff) | 0x4000);
}

unsigned cAD9854selfstate(val v)
{
  return (cAD9854state(v) | 0x0200);
}

unsigned cAD9854fsk(val v)
{
  return v.bval ? 0x2000 : 0;
}

unsigned cGFIBtrig(val v)
{
  return ((v.ival & 0x8000) | 0x8000);
}

unsigned cDAC0state(val v)
{
  return ((v.ival & 0x7ff) | 0x4000);
}

unsigned cDAC1state(val v)
{
  return (cDAC0state(v) | 0x800);
}

unsigned cDAC2state(val v)
{
  return (cDAC0state(v) | 0x1000);
}

unsigned cDAC3state(val v)
{
  return (cDAC0state(v) | 0x1800);
}

unsigned cDAC0selfstate(val v)
{
  return ((v.ival & 0x7ff) | 0x6000);
}

unsigned cDAC1selfstate(val v)
{
  return (cDAC0selfstate(v) | 0x800);
}

unsigned cDAC2selfstate(val v)
{
  return (cDAC0selfstate(v) | 0x1000);
}

unsigned cDAC3selfstate(val v)
{
  return (cDAC0selfstate(v) | 0x1800);
}

unsigned cTTLD0(val v)
{
  return v.bval ? 0x1 : 0;
}

unsigned cTTLD1(val v)
{
  return v.bval ? 0x2 : 0;
}

unsigned cTTLD2(val v)
{
  return v.bval ? 0x4 : 0;
}

unsigned cTTLD3(val v)
{
  return v.bval ? 0x8 : 0;
}

unsigned cTTLD4(val v)
{
  return v.bval ? 0x10 : 0;
}

unsigned cTTLD5(val v)
{
  return v.bval ? 0x20 : 0;
}

unsigned cTTLD6(val v)
{
  return v.bval ? 0x40 : 0;
}

unsigned cTTLD7(val v)
{
  return v.bval ? 0x80 : 0;
}

unsigned cTTLD8(val v)
{
  return v.bval ? 0x100 : 0;
}

unsigned cTTLD9(val v)
{
  return v.bval ? 0x200 : 0;
}

unsigned cTTLD10(val v)
{
  return v.bval ? 0x400 : 0;
}

unsigned cTTLD11(val v)
{
  return v.bval ? 0x800 : 0;
}

unsigned cTTLD12(val v)
{
  return v.bval ? 0x1000 : 0;
}

unsigned cTTLD13(val v)
{
  return v.bval ? 0x2000 : 0;
}

unsigned cTTLD14(val v)
{
  return v.bval ? 0x4000 : 0;
}

unsigned cTTLD15(val v)
{
  return v.bval ? 0x8000 : 0;
}

unsigned cDAC8(val v)
{
  double aux=v.fval;
  unsigned dacout,neg=0;

  if(aux<0)
    {
      neg=1;
      aux=-aux;
    }

  dacout=(aux*32768./15.);

  if(neg)
    dacout=0x10000-dacout;

  return dacout;
}


void InitFunList()
{
  action *p;
  int i;

  for(i=0;i<FUNLISTSIZE;FunList[i++].id=0);
  for(i=0;i<ADDRSPACE;GFIBcs[i++]=0);

  //Generic GFIB write
  p=&FunList[iTest];
  p->ds="GFIB";
  p->cn="Test: None";
  p->un="";
  p->type=TEST_A;
  p->id=iTest;
  p->fam=fTest;
  p->gfib.addr=0;
  p->gfib.mask=0xffff;
  p->compile=cTest;

//////////////////////////////////////////////////////////////////
//		DDS1 ad9958 (GFIB #2)				//
//////////////////////////////////////////////////////////////////
  p=&FunList[iDDS1State];
  p->ds="DDS #1 State";
  p->cn="DDS #1 State";
  p->type=ENUM_A;
  p->id=iDDS1State;
  p->cval.ival=0;
  p->fam=fDDS1State;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxstate;

  p=&FunList[iDDS1SelfState];
  p->ds="DDS #1 Self State";
  p->cn="DDS #1 Self State";
  p->type=ENUM_A;
  p->id=iDDS1SelfState;
  p->fam=fDDS1SelfState;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxselfstate;

 p=&FunList[iDDS1RampCh0];
  p->ds="DDS #1 Ramp Ch0";
  p->cn="DDS #1 Ramp Ch0";
  p->type=BINARY_A;
  p->id=iDDS1RampCh0;
  p->fam=fDDS1Ramp;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0;

  p=&FunList[iDDS1RampCh1];
  p->ds="DDS #1 Ramp Ch1";
  p->cn="DDS #1 Ramp Ch1";
  p->type=BINARY_A;
  p->id=iDDS1RampCh1;
  p->fam=fDDS1Ramp;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh1;

  p=&FunList[iDDS1RampCh0Ch1];
  p->ds="DDS #1 Ramp Ch0 & Ch1";
  p->cn="DDS #1 Ramp Ch0 & Ch1";
  p->type=BINARY_A;
  p->id=iDDS1RampCh0Ch1;
  p->fam=fDDS1Ramp;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0Ch1;

  p=&FunList[iDDS1Trig];
  p->ds="DDS #1 Trigger";
  p->cn="DDS #1 Trigger";
  p->type=SIMPLE_A;
  p->id=iDDS1Trig;
  p->fam=fDDS1Trig;
  p->gfib.addr=2;
  p->gfib.mask=0xffff;
  p->compile=cGFIBtrig;

//////////////////////////////////////////////////////////////////
//		DDS4 (GFIB #6) with ramps			//
//////////////////////////////////////////////////////////////////
  p=&FunList[iDDS4State];
  p->ds="DDS #4 State";
  p->cn="DDS #4 State";
  p->type=ENUM_A;
  p->id=iDDS4State;
  p->cval.ival=0;
  p->fam=fDDS4State;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxstate;

  p=&FunList[iDDS4SelfState];
  p->ds="DDS #4 Self State";
  p->cn="DDS #4 Self State";
  p->type=ENUM_A;
  p->id=iDDS4SelfState;
  p->fam=fDDS4SelfState;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxselfstate;

  p=&FunList[iDDS4RampCh0];
  p->ds="DDS #4 Ramp Ch0";
  p->cn="DDS #4 Ramp Ch0";
  p->type=BINARY_A;
  p->id=iDDS4RampCh0;
  p->fam=fDDS4Ramp;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0;

  p=&FunList[iDDS4RampCh1];
  p->ds="DDS #4 Ramp Ch1";
  p->cn="DDS #4 Ramp Ch1";
  p->type=BINARY_A;
  p->id=iDDS4RampCh1;
  p->fam=fDDS4Ramp;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh1;

  p=&FunList[iDDS4RampCh0Ch1];
  p->ds="DDS #4 Ramp Ch0 & Ch1";
  p->cn="DDS #4 Ramp Ch0 & Ch1";
  p->type=BINARY_A;
  p->id=iDDS4RampCh0Ch1;
  p->fam=fDDS4Ramp;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0Ch1;

  p=&FunList[iDDS4Trig];
  p->ds="DDS #4 Trigger";
  p->cn="DDS #4 Trigger";
  p->type=SIMPLE_A;
  p->id=iDDS4Trig;
  p->fam=fDDS4Trig;
  p->gfib.addr=6;
  p->gfib.mask=0xffff;
  p->compile=cGFIBtrig;


//////////////////////////////////////////////////////////////////
//		DDS4 (GFIB #7) with ramps			//
//////////////////////////////////////////////////////////////////
  p=&FunList[iDDS5State];
  p->ds="DDS #5 State";
  p->cn="DDS #5 State";
  p->type=ENUM_A;
  p->id=iDDS5State;
  p->cval.ival=0;
  p->fam=fDDS5State;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxstate;

  p=&FunList[iDDS5SelfState];
  p->ds="DDS #5 Self State";
  p->cn="DDS #5 Self State";
  p->type=ENUM_A;
  p->id=iDDS5SelfState;
  p->fam=fDDS5SelfState;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->gfib.smax=512;
  p->compile=cAD9958dxselfstate;

  p=&FunList[iDDS5RampCh0];
  p->ds="DDS #5 Ramp Ch0";
  p->cn="DDS #5 Ramp Ch0";
  p->type=BINARY_A;
  p->id=iDDS5RampCh0;
  p->fam=fDDS5Ramp;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0;

  p=&FunList[iDDS5RampCh1];
  p->ds="DDS #5 Ramp Ch1";
  p->cn="DDS #5 Ramp Ch1";
  p->type=BINARY_A;
  p->id=iDDS5RampCh1;
  p->fam=fDDS5Ramp;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh1;

  p=&FunList[iDDS5RampCh0Ch1];
  p->ds="DDS #5 Ramp Ch0 & Ch1";
  p->cn="DDS #5 Ramp Ch0 & Ch1";
  p->type=BINARY_A;
  p->id=iDDS5RampCh0Ch1;
  p->fam=fDDS5Ramp;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->compile=cAD9958dxRampCh0Ch1;

  p=&FunList[iDDS5Trig];
  p->ds="DDS #5 Trigger";
  p->cn="DDS #5 Trigger";
  p->type=SIMPLE_A;
  p->id=iDDS5Trig;
  p->fam=fDDS5Trig;
  p->gfib.addr=7;
  p->gfib.mask=0xffff;
  p->compile=cGFIBtrig;


//////////////////////////////////////////////////////////////////
//		DAC8_1 (GFIB #64-71)				//
//////////////////////////////////////////////////////////////////

  p=&FunList[iAOM_3DMOT_Down];
  p->ds="DAC8 #1 AOM 3DMOT Down";
  p->cn="DAC8 #1 Self Ch. 0: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iAOM_3DMOT_Down;
  p->fam=fBRD1DAC0SelfState;
  p->compile=cDAC8;
  p->gfib.addr=64;
  p->gfib.mask=0xffff;

  p=&FunList[iAOM_3DMOT_Up];
  p->ds="DAC8 #1 AOM 3DMOT Up";
  p->cn="DAC8 #1 Self Ch. 1: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iAOM_3DMOT_Up;
  p->fam=fBRD1DAC1SelfState;
  p->compile=cDAC8;
  p->gfib.addr=65;
  p->gfib.mask=0xffff;

  p=&FunList[iAOM_Det];
  p->ds="DAC8 #1 AOM Detection";
  p->cn="DAC8 #1 Self Ch. 2: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iAOM_Det;
  p->fam=fBRD1DAC2SelfState;
  p->compile=cDAC8;
  p->gfib.addr=66;
  p->gfib.mask=0xffff;

  p=&FunList[iAOM_Raman1];
  p->ds="DAC8 #1 AOM_Raman1";
  p->cn="DAC8 #1 Self Ch. 3: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iAOM_Raman1;
  p->fam=fBRD1DAC3SelfState;
  p->compile=cDAC8;
  p->gfib.addr=67;
  p->gfib.mask=0xffff;

  p=&FunList[iAOM_Raman2];
  p->ds="DAC8 #1 AOM_Raman2";
  p->cn="DAC8 #1 Self Ch. 4: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iAOM_Raman2;
  p->fam=fBRD1DAC4SelfState;
  p->compile=cDAC8;
  p->gfib.addr=68;
  p->gfib.mask=0xffff;

  p=&FunList[iBRD1DAC5SelfState];
  p->ds="DAC8 #1 Self Ch. 5";
  p->cn="DAC8 #1 Self Ch. 5: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD1DAC5SelfState;
  p->fam=fBRD1DAC5SelfState;
  p->compile=cDAC8;
  p->gfib.addr=69;
  p->gfib.mask=0xffff;
  
  p=&FunList[iVCA_3DMOT_Down];
  p->ds="DAC8 #1 VCA_3DMOT_Down";
  p->cn="DAC8 #1 Self Ch. 6: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iVCA_3DMOT_Down;
  p->fam=fBRD1DAC6SelfState;
  p->compile=cDAC8;
  p->gfib.addr=70;
  p->gfib.mask=0xffff;

  p=&FunList[iVCA_3DMOT_Up];
  p->ds="DAC8 #1 VCA_3DMOT_Up";
  p->cn="DAC8 #1 Self Ch. 7: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iVCA_3DMOT_Up;
  p->fam=fBRD1DAC7SelfState;
  p->compile=cDAC8;
  p->gfib.addr=71;
  p->gfib.mask=0xffff;

//////////////////////////////////////////////////////////////////
//		DAC8_2 (GFIB #72-79)				//
//////////////////////////////////////////////////////////////////

  p=&FunList[iBRD2DAC0SelfState];
  p->ds="DAC8 #2 Self Ch. 0";
  p->cn="DAC8 #2 Self Ch. 0: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD2DAC0SelfState;
  p->fam=fBRD2DAC0SelfState;
  p->compile=cDAC8;
  p->gfib.addr=72;
  p->gfib.mask=0xffff;

  p=&FunList[iBias_X];
  p->ds="DAC8 #2 Bias_X";
  p->cn="DAC8 #2 Bias_X: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBias_X;
  p->fam=fBRD2DAC1SelfState;
  p->compile=cDAC8;
  p->gfib.addr=73;
  p->gfib.mask=0xffff;

  p=&FunList[iBRD2DAC2SelfState];
  p->ds="DAC8 #2 Self Ch. 2";
  p->cn="DAC8 #2 Self Ch. 2: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD2DAC2SelfState;
  p->fam=fBRD2DAC2SelfState;
  p->compile=cDAC8;
  p->gfib.addr=74;
  p->gfib.mask=0xffff;

  p=&FunList[iBias_Y];
  p->ds="DAC8 #2 Bias_Y";
  p->cn="DAC8 #2 Bias_Y: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBias_Y;
  p->fam=fBRD2DAC3SelfState;
  p->compile=cDAC8;
  p->gfib.addr=75;
  p->gfib.mask=0xffff;

  p=&FunList[iBRD2DAC4SelfState];
  p->ds="DAC8 #2 Self Ch. 4";
  p->cn="DAC8 #2 Self Ch. 4: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD2DAC4SelfState;
  p->fam=fBRD2DAC4SelfState;
  p->compile=cDAC8;
  p->gfib.addr=76;
  p->gfib.mask=0xffff;

  p=&FunList[iBias_Z];
  p->ds="DAC8 #2 Bias_Z";
  p->cn="DAC8 #2 Bias_Z: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBias_Z;
  p->fam=fBRD2DAC5SelfState;
  p->compile=cDAC8;
  p->gfib.addr=77;
  p->gfib.mask=0xffff;
  
  p=&FunList[iBRD2DAC6SelfState];
  p->ds="DAC8 #2 Self Ch. 6";
  p->cn="DAC8 #2 Self Ch. 6: Board 7";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD2DAC6SelfState;
  p->fam=fBRD2DAC6SelfState;
  p->compile=cDAC8;
  p->gfib.addr=78;
  p->gfib.mask=0xffff;

  p=&FunList[iBRD2DAC7SelfState];
  p->ds="DAC8 #2 Self Ch. 7";
  p->cn="DAC8 #2 Self Ch. 7: Board 6";
  p->type=SCALAR_A;
  p->min=-12.;
  p->max=12.;
  p->fm="%2.4f";
  p->id=iBRD2DAC7SelfState;
  p->fam=fBRD2DAC7SelfState;
  p->compile=cDAC8;
  p->gfib.addr=79;
  p->gfib.mask=0xffff;



//////////////////////////////////////////////////////////////////
//		DIGITAL OUTPUT (GFIB #1)			//
//////////////////////////////////////////////////////////////////
  p=&FunList[iRaman_Dw_Shutter];
  p->ds="TTL1 D0    Raman Down";
  p->cn="TTL1 D0: Board1";
  p->type=BINARY_A;
  p->id=iRaman_Dw_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0001;
  p->compile=cTTLD0;

  p=&FunList[iRaman_Up_Shutter];
  p->ds="TTL1 D1    Raman Up";
  p->cn="TTL1 D1: Board 1";
  p->type=BINARY_A;
  p->id=iRaman_Up_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0002;
  p->compile=cTTLD1;

  p=&FunList[iRepump_MOT_Shutter];
  p->ds="TTL1 D2     Repump MOT";
  p->cn="TTL1 D2: Board 1";
  p->type=BINARY_A;
  p->id=iRepump_MOT_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0004;
  p->compile=cTTLD2;

  p=&FunList[iRepump_Push_Shutter];
  p->ds="TTL1 D3     Repump Push";
  p->cn="TTL1 D3: Board 1";
  p->type=BINARY_A;
  p->id=iRepump_Push_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0008;
  p->compile=cTTLD3;

  p=&FunList[iRepump_Det_Shutter];
  p->ds="TTL1 D4     Repump Det";
  p->cn="TTL1 D4: Board 1";
  p->type=BINARY_A;
  p->id=iRepump_Det_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0010;
  p->compile=cTTLD4;

  p=&FunList[iDetection_Shutter];
  p->ds="TTL1 D5     Detection";
  p->cn="TTL1 D5: Board 1";
  p->type=BINARY_A;
  p->id=iDetection_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0020;
  p->compile=cTTLD5;

  p=&FunList[i3DMOT_Up_Shutter];
  p->ds="TTL1 D6     3DMOT Up";
  p->cn="TTL1 D6: Board 1";
  p->type=BINARY_A;
  p->id=i3DMOT_Up_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0040;
  p->compile=cTTLD6;

  p=&FunList[i3DMOT_Down_Shutter];
  p->ds="TTL1 D7     3DMOT Down";
  p->cn="TTL1 D7: Board 1";
  p->type=BINARY_A;
  p->id=i3DMOT_Down_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0080;
  p->compile=cTTLD7;

  p=&FunList[i2DMOT_Shutter ];
  p->ds="TTL1 D8     2DMOT";
  p->cn="TTL1 D8: Board 1";
  p->type=BINARY_A;
  p->id=i2DMOT_Shutter;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0100;
  p->compile=cTTLD8;

  p=&FunList[iAOM_Raman1_Switch];
  p->ds="TTL1 D9     AOM_Raman1";
  p->cn="TTL1 D9: Board 1";
  p->type=BINARY_A;
  p->id=iAOM_Raman1_Switch;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0200;
  p->compile=cTTLD9;

  p=&FunList[iAOM_Raman2_Switch];
  p->ds="TTL1 D10    AOM_Raman2";
  p->cn="TTL1 D10: Board 1";
  p->type=BINARY_A;
  p->id=iAOM_Raman2_Switch;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0400;
  p->compile=cTTLD10;

  p=&FunList[iAOM_3DMOT_Up_Switch];
  p->ds="TTL1 D11   AOM 3DMOT Up";
  p->cn="TTL1 D11: Board 1";
  p->type=BINARY_A;
  p->id=iAOM_3DMOT_Up_Switch;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x0800;
  p->compile=cTTLD11;

  p=&FunList[iAOM_Det_Switch];
  p->ds="TTL1 D12   AOM Detection";
  p->cn="TTL1 D12: Board 1";
  p->type=BINARY_A;
  p->id=iAOM_Det_Switch;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x1000;
  p->compile=cTTLD12;

  p=&FunList[iAOM_3DMOT_Down_Switch];
  p->ds="TTL1 D13   AOM 3DMOT Down";
  p->cn="TTL1 D13: Board 1";
  p->type=BINARY_A;
  p->id=iAOM_3DMOT_Down_Switch;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x2000;
  p->compile=cTTLD13;

  p=&FunList[iTTL1D14];
  p->ds="TTL1 D14";
  p->cn="TTL1 D14: Board 1";
  p->type=BINARY_A;
  p->id=iTTL1D14;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x4000;
  p->compile=cTTLD14;

  p=&FunList[iTTL1D15];
  p->ds="TTL1 D15";
  p->cn="TTL1 D15: Board 1";
  p->type=BINARY_A;
  p->id=iTTL1D15;
  p->fam=fTTL1D;
  p->gfib.addr=1;
  p->gfib.mask=0x8000;
  p->compile=cTTLD15;

//////////////////////////////////////////////////////////////////
//		DIGITAL OUTPUT 2 (GFIB #5)			//
//////////////////////////////////////////////////////////////////
  p=&FunList[iExp_Trig];
  p->ds="TTL2 D0    Experiment Trig";
  p->cn="TTL2 D0: Board 5";
  p->type=BINARY_A;
  p->id=iExp_Trig;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0001;
  p->compile=cTTLD0;

  p=&FunList[iTTL2D1];
  p->ds="TTL2 D1";
  p->cn="TTL2 D1: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D1;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0002;
  p->compile=cTTLD1;

  p=&FunList[iTTL2D2];
  p->ds="TTL2 D2";
  p->cn="TTL2 D2: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D2;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0004;
  p->compile=cTTLD2;

  p=&FunList[iBragg_up];
  p->ds="TTL2 D3    Bragg Up";
  p->cn="TTL2 D3: Board 5";
  p->type=BINARY_A;
  p->id=iBragg_up;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0008;
  p->compile=cTTLD3;

  p=&FunList[iBragg_Down];
  p->ds="TTL2 D4    Bragg Down";
  p->cn="TTL2 D4: Board 5";
  p->type=BINARY_A;
  p->id=iBragg_Down;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0010;
  p->compile=cTTLD4;

  p=&FunList[iBias_Coils];
  p->ds="TTL2 D5    Bias Coils";
  p->cn="TTL2 D5: Board 5";
  p->type=BINARY_A;
  p->id=iBias_Coils;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0020;
  p->compile=cTTLD5;

  p=&FunList[iBias_Bars];
  p->ds="TTL2 D6    Bias_Bars";
  p->cn="TTL2 D6: Board 5";
  p->type=BINARY_A;
  p->id=iBias_Bars;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0040;
  p->compile=cTTLD6;

  p=&FunList[i3DMOT_Coils];
  p->ds="TTL2 D7    3DMOT_Coils";
  p->cn="TTL2 D7: Board 5";
  p->type=BINARY_A;
  p->id=i3DMOT_Coils;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0080;
  p->compile=cTTLD7;

  p=&FunList[iRedpitaya_Top];
  p->ds="TTL2 D8    Redpitaya";
  p->cn="TTL2 D8: Board 5";
  p->type=BINARY_A;
  p->id=iRedpitaya_Top;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0100;
  p->compile=cTTLD8;

  p=&FunList[iTTL2D9];
  p->ds="TTL2 D9";
  p->cn="TTL2 D9: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D9;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0200;
  p->compile=cTTLD9;

  p=&FunList[iTTL2D10];
  p->ds="TTL2 D10";
  p->cn="TTL2 D10: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D10;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0400;
  p->compile=cTTLD10;

  p=&FunList[iTTL2D11];
  p->ds="TTL2 D11";
  p->cn="TTL2 D11: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D11;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x0800;
  p->compile=cTTLD11;

  p=&FunList[iTTL2D12];
  p->ds="TTL2 D12";
  p->cn="TTL2 D12: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D12;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x1000;
  p->compile=cTTLD12;

  p=&FunList[iTTL2D13];
  p->ds="TTL2 D13";
  p->cn="TTL2 D13: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D13;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x2000;
  p->compile=cTTLD13;

  p=&FunList[iTTL2D14];
  p->ds="TTL2 D14";
  p->cn="TTL2 D14: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D14;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x4000;
  p->compile=cTTLD14;

  p=&FunList[iTTL2D15];
  p->ds="TTL2 D15";
  p->cn="TTL2 D15: Board 5";
  p->type=BINARY_A;
  p->id=iTTL2D15;
  p->fam=fTTL2D;
  p->gfib.addr=5;
  p->gfib.mask=0x8000;
  p->compile=cTTLD15;
}
