import os
import glob
import subprocess
import sys
import codecs
import re
import io
from os import listdir
from os.path import isfile, isdir, join
import logging
from time import strftime
import argparse

PART_NUM_FILE_NAME = "part_numbers.txt"
WORD = "AurixBox"
SBL_TYPE = "SBL"
ECU_NAME = "Aurix" #??
ECU_PIN ='1301' #??
ECU_SECURITY_KEY = 'FFFFFFFF55' #??
SWDL_TARGET = 'Virtual Channel 1' #??

SWDLTOOL_EXE = 'SWDLTool.exe'
SWDLTOOL_PATH = 'C:\Program Files (x86)\SWDL\\'

# Dictionary containing all error messages from the SWDL tool chain.
_SWDL_MSG = {
    10: 'SwdlTool: Bad arguments',
    20: 'SwdlTool: Error connecting to device',
    30: 'SwdlTool: Error disconnecting to device',
    40: 'SwdlTool: Error downloading to device; Unknown reason',
    41: 'SwdlTool: Error downloading to device; Aborted by user',
    42: 'SwdlTool: Error downloading to device; Could not enter programming session',
    43: 'SwdlTool: Error downloading to device; Pre Programming failed',
    44: 'SwdlTool: Error downloading to device; Programming App failed',
    45: 'SwdlTool: Error downloading to device; Programming Sbl failed',
    46: 'SwdlTool: Error downloading to device; Erase memory failed',
    47: 'SwdlTool: Error downloading to device; Activate Sbl failed',
    48: 'SwdlTool: Error downloading to device; Complete and compatible check failed',
    49: 'SwdlTool: Error downloading to device; Post Programming failed',
    50: 'SwdlTool: Error downloading to device; Security access failed',
    51: 'SwdlTool: Error downloading to device; Download not started',
    52: 'SwdlTool: Error downloading to device; Download failed',
    53: 'SwdlTool: Error downloading to device; Programming preconditions check failed',
    54: 'SwdlTool: Error downloading to device; Diagnostic session failed',
    55: 'SwdlTool: Error downloading to device; Response timeout',
    56: 'SwdlTool: Error downloading to device; Read Data identifier failed',
    57: 'SwdlTool: Error downloading to device; Invalid security key (pin code)',
    58: 'SwdlTool: Error downloading to device; Security access denied'
}

parser = argparse.ArgumentParser(description="Handles downloading of VBF files to the ADPM Rig target")
parser.add_argument("-w", "--workspacepath", action='store', help="Specifies the path to the Jenkins workspace to use", required=True)
parser.add_argument("-v", "--vbsfilepath", action='store', help="Specifies the bootloader to use", required=True)
args = parser.parse_args()

VBF_FILES_DIRECTORY = args.workspacepath
VBS_FILE_PATH = args.vbsfilepath
SWDLTool_PATH = "C:\SK\ContinuosIntegration\SWDLTool_V2.1.0.13_2016-09-29\Release"
SBL_FILE_PATH = "C:\SK\VolvoCars\AS_HIL\CI\ADPM\SWDL_TestFiles\SBLFile"
LOG_FILE_PATH = "C:\SK\VolvoCars\AS_HIL\CI\ADPM\Python\AurixLogs"
SWDL_VBS_FILE_NAME = "Aurix_Vbs.vbs"

# set up logging to file
logfile = os.path.join(LOG_FILE_PATH, strftime("AdpmSwdl_%m_%d_%Y_%H%M%S.log"))
logging.basicConfig(level=logging.DEBUG,
                    format='%(message)s',
                    datefmt='',
                    filename=logfile,
                    filemode='w')

def start_swdl():
 '''
  Start software download to  ECU using SWDL tool.
 '''
 vbs_file = create_vbs_file()
 print(vbs_file)
 device_index = get_device_index(SWDL_TARGET, False)
 print("\ndevice_index =",device_index )
 swdl_verify_connection(device_index)
 download_to_target(device_index,vbs_file)

def swdl_tool(flags, print_stdout):
 stdout = stderr = b''
 cmdline = os.path.join(SWDLTool_PATH, SWDLTOOL_EXE)  # Join info to make a path
 cmdline = os.path.normpath(cmdline)  # Normalize the path to actual OS
 cmdline = [cmdline]  # Make path part of a list
 cmdline.extend(flags)  # Add needed flags to the command

 swdltool_process = subprocess.Popen(cmdline, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=SWDLTool_PATH)

 lines_iterator = iter(swdltool_process.stdout.readline, '')
 for line in lines_iterator:
  if line != b'':
   if print_stdout:
    print(line.decode().rstrip('\r\n'))
   stdout += line
   #print(stdout)
   #swdl_logging(stdout)
  if line == b'' and swdltool_process.poll() is not None:
   break
 exitcode = swdltool_process.wait()
 #print("Exitcode code=",exitcode)
 return exitcode, stdout, stderr


def get_device_index(connection_name, trace):
 # Get a list of all available devices
 (exitcode, stdout, _) = swdl_tool(['list'], trace)

 #print("\ngetIndex exitcode=",exitcode)
 log = "\nexitcode while getting index of the device connected " + str(exitcode)
 swdl_logging(log)

 stdout = stdout.decode()
 devices = stdout.splitlines()

 #print(devices)
 swdl_logging(devices)

 # an error code was returned from SwdlTool
 if(exitcode > 0):
  print("Cannot get the index")
  exit(-1)

 # Get the device index for the given device name
 index = [i for i, x in enumerate(devices) if x.find(connection_name) != -1]

 if(index == -1):
  #print('\nERROR: Device `%s` does not exist!' % SWDL_TARGET)
  log = '\nERROR: Device `%s` does not exist!' % SWDL_TARGET
  swdl_logging(log)
  exit(-1)

 return index[0]

def swdl_verify_connection(index):
 # Call SwdlTool with the right options
 (exitcode, _, _) = swdl_tool(['connection-test', str(index)], False)
 #print('\nverify-exitcode `%s`' + exitcode)
 swdl_logging('\nverify-exitcode ' + str(exitcode))
 # If an error code was returned from SwdlTool, print out error information and exit the script

 if (exitcode > 0):
  print("Connection verification failed")
  exit(-6)

def download_to_target(index, vbs_file):
 show_dl_info = True

 # Verify that the vbs file exist, if not print out error message and exit the script
 #if(os.path.abspath(os.path.isfile(vbs_file) != 0)):
 if not isfile(vbs_file):
  print("ERROR: The vbs file `%s` does not exist" % vbs_file)
  exit(-5)

 # Call SwdlTool with the right options
 exitcode, _, _ = swdl_tool(
  ['download', '-i', str(ECU_PIN), str(ECU_SECURITY_KEY), str(index), vbs_file], show_dl_info
 )

 # If an error code was returned from SwdlTool, print out error information and exit the script
 if (exitcode > 0):
  print("\nError! Software download fails= " + str(exitcode))
  swdl_logging("\nError! Software download fails= " + str(exitcode))
  exit(-3)
 else:
  print("\nSuccessfully downloaded files ")
  swdl_logging("\nSuccessfully downloaded files to ECU")


def read_download_filelist():
 try:
  file_list = []
  partnum_folder = VBF_FILES_DIRECTORY
  partnum_file   = os.path.join(partnum_folder,PART_NUM_FILE_NAME)

  with codecs.open(partnum_file, encoding='utf-8',mode='r') as file:
   for line in file:
    if WORD in line:
     #print(line)
     file = line.decode().rstrip('\r\n').rsplit(None, 1)[-1]
     vbf_file = os.path.join(VBF_FILES_DIRECTORY,file)
     file_list.append(vbf_file)
   #print(file_list)
   return file_list

 except IOError as err:
  sys.exit(-1)

def find_sbl_file():
 # Search SBL file from the sbl file path
 files = [f for f in listdir(SBL_FILE_PATH) if isfile(join(SBL_FILE_PATH , f))]
 files = [f for f in files if f.endswith(".vbf")]

 # search trough all vbf files to find out which one of them is the secondary boot loader
 SBLFile = ''
 for filename in files:
  file = open(SBL_FILE_PATH + '/' + filename, 'rb')
  for lineNumber in range(0, 40):
   line = file.readline(100)
   #if line.find(b'}') != -1:
   if line.find(SBL_TYPE) != -1:
    SBLFile = filename
  file.close()
  if SBLFile != '':
   break
 return SBLFile

def create_vbs_file():
 try:
  updated_file_list = []

  #Find SBL file from the sbl file path
  sbl_file = find_sbl_file()
  if sbl_file == '':
   #print('VCC_ERROR: Could not find the secondary bootloader in "' + SBL_FILE_PATH  + '"')
   swdl_logging('Could not find the sbl file in "' + SBL_FILE_PATH + '"')
   exit(-4)

  sbl_file = os.path.join(SBL_FILE_PATH, sbl_file)
  vbs_folder = os.path.abspath(VBS_FILE_PATH )
  vbs_file = os.path.join(vbs_folder, SWDL_VBS_FILE_NAME)

  # Create the vbs file and add all vbf files to it, starting with the boot loader.
  f = io.open(vbs_file, 'w', encoding='utf-8')
  f.write(sbl_file + u'\n')

  #print(updated_file_list)
  file_list = read_download_filelist()
  for i, file in enumerate(file_list):
   f.write(file + u'\n')

  return(vbs_file)

 except IOError as err:
  print("\nFile open error")
  exit(-1)


def swdl_logging(log):
 logger = logging.getLogger('Aurix log')
 # create file handler which logs even debug messages
 fh = logging.FileHandler(logfile)
 fh.setLevel(logging.DEBUG)

 # create console handler with a higher log level
 #ch = logging.StreamHandler()
 #ch.setLevel(logging.ERROR)

 #logger.addHandler(ch)
 logger.addHandler(fh)

 logger.error(log)
 #logger.error(log)

def main():
 start_swdl()

if __name__ == '__main__':
 main()  
    
    
