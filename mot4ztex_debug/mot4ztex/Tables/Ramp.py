import numpy as np
import scipy
import matplotlib.pyplot as plt

ListT=list(np.linspace(0,5000,5001))
Listx0=list(np.linspace(0,10,1001))
Listx1=list(np.linspace(0,10,1001))
Listx2=list(np.linspace(0,10,1001))
Listx3=list(np.linspace(0,10,1001))
nstep=[0,0,0,0]

def ramp1(xi0,xf0,T0,dt0,xi1,xf1,T1,dt1,xi2,xf2,T2,dt2,xi3,xf3,T3,dt3):
    global Listx0,Listx1,Listx2,Listx3,ListT,nstep
    xi=[xi0,xi1,xi2,xi3]
    xf=[xf0,xf1,xf2,xf3]
    T=[T0,T1,T2,T3]
    dt=[dt0,dt1,dt2,dt3]
    dx=[0,0,0,0]
    for i in range(0,4):
        nstep[i]=int(T[i]/dt[i])
        dt[i]=T[i]/nstep[i]
        dx[i]=(xf[i]-xi[i])/(nstep[i]-1)
    for i in range(0,nstep[0]):
        Listx0.append(round((xi[0]+i*dx[0]),2))
    for i in range(0,nstep[1]):
        Listx1.append(round((xi[1]+i*dx[1]),2))
    for i in range(0,nstep[2]):
        Listx2.append(round((xi[2]+i*dx[2]),2))
    for i in range(0,nstep[3]):
        Listx3.append(round((xi[3]+i*dx[3]),2))

    for i in range(nstep[0]+1,len(ListT)):
        Listx0.append(0)
    for i in range(nstep[1]+1,len(ListT)):
        Listx1.append(0)
    for i in range(nstep[2]+1,len(ListT)):
        Listx2.append(0)
    for i in range(nstep[3]+1,len(ListT)):
        Listx3.append(0)
    
    with open('table_DAC1.dat', 'w') as f:
        for i in range(len(ListT)):
            f.write('{:4.0f} {:.2f} {:.2f} {:.2f} {:.2f}\n'.format(ListT[i], Listx0[i], Listx1[i], Listx2[i], Listx3[i]))

    print('Ramp DAC1 from state 1001 to states')
    print(np.array(nstep)+1000)

def ramp2(xi0,xf0,T0,dt0,xi1,xf1,T1,dt1,xi2,xf2,T2,dt2,xi3,xf3,T3,dt3):
    global Listx0,Listx1,Listx2,Listx3,ListT,nstep
    xi=[xi0,xi1,xi2,xi3]
    xf=[xf0,xf1,xf2,xf3]
    T=[T0,T1,T2,T3]
    dt=[dt0,dt1,dt2,dt3]
    dx=[0,0,0,0]
    for i in range(0,4):
        nstep[i]=int(T[i]/dt[i])
        dt[i]=T[i]/nstep[i]
        dx[i]=(xf[i]-xi[i])/(nstep[i]-1)
    for i in range(0,nstep[0]):
        Listx0.append(round((xi[0]+i*dx[0]),2))
    for i in range(0,nstep[1]):
        Listx1.append(round((xi[1]+i*dx[1]),2))
    for i in range(0,nstep[2]):
        Listx2.append(round((xi[2]+i*dx[2]),2))
    for i in range(0,nstep[3]):
        Listx3.append(round((xi[3]+i*dx[3]),2))

    for i in range(nstep[0]+1,len(ListT)):
        Listx0.append(0)
    for i in range(nstep[1]+1,len(ListT)):
        Listx1.append(0)
    for i in range(nstep[2]+1,len(ListT)):
        Listx2.append(0)
    for i in range(nstep[3]+1,len(ListT)):
        Listx3.append(0)
    
    with open('table_DAC2.dat', 'w') as f:
        for i in range(len(ListT)):
            f.write('{:4.0f} {:.2f} {:.2f} {:.2f} {:.2f}\n'.format(ListT[i], Listx0[i], Listx1[i], Listx2[i], Listx3[i]))

    print('Ramp DAC2 from state 1001 to states')
    print(np.array(nstep)+1000)
        
ramp1(10000,100,1000,10,300,10,1000,5,6,0,1000,50,6,0,1000,20)
ramp2(10000,100,1000,10,300,10,1000,5,6,0,1000,50,6,0,1000,20)
