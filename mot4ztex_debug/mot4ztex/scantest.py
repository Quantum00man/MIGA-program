import os

def scan(): #K Scan and give values to the interface
        
    os.system('rm /var/lock/mot*')
    os.system('./tmot4 -f test1_DDS.mot')

scan()

