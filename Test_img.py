from __future__ import print_function
import argparse
import os
import random
import torch
import torch.nn as nn
import torch.nn.parallel
import torch.backends.cudnn as cudnn
import torch.optim as optim
import torch.utils.data
from torch.autograd import Variable
import torch.nn.functional as F
import skimage
import skimage.io
import skimage.transform
import numpy as np
import time
import math
from utils import preprocess 
from models import *
import cv2

# 2012 data /media/jiaren/ImageNet/data_scene_flow_2012/testing/

parser = argparse.ArgumentParser(description='PSMNet')
parser.add_argument('--KITTI', default='2015',
                    help='KITTI version')
parser.add_argument('--datapath', default='/media/jiaren/ImageNet/data_scene_flow_2015/testing/',
                    help='select model')
parser.add_argument('--loadmodel', default='./trained/pretrained_model_KITTI2015.tar',
                    help='loading model')
parser.add_argument('--leftimg', default= None,
                    help='load model')
parser.add_argument('--rightimg', default= None,
                    help='load model')   
parser.add_argument('--isgray', default= False,
                    help='load model')                                       
parser.add_argument('--model', default='stackhourglass',
                    help='select model')
parser.add_argument('--maxdisp', type=int, default=192,
                    help='maxium disparity')
parser.add_argument('--no-cuda', action='store_true', default=False,
                    help='enables CUDA training')
parser.add_argument('--seed', type=int, default=1, metavar='S',
                    help='random seed (default: 1)')
args = parser.parse_args()
args.cuda = not args.no_cuda and torch.cuda.is_available()

torch.manual_seed(args.seed)
if args.cuda:
    torch.cuda.manual_seed(args.seed)
#test_left_img, test_right_img = DA.dataloader(args.datapath)

if args.model == 'stackhourglass':
    model = stackhourglass(args.maxdisp)
elif args.model == 'basic':
    model = basic(args.maxdisp)
else:
    print('no model')

model = nn.DataParallel(model, device_ids=[0])
model.cuda()


if args.loadmodel is not None:
    print('load PSMNet')
    state_dict = torch.load(args.loadmodel)
    model.load_state_dict(state_dict['state_dict'])

print('Number of model parameters: {}'.format(sum([p.data.nelement() for p in model.parameters()])))

def test(imgL,imgR):
        if args.cuda:
           print('use cuda')
           imgL = torch.FloatTensor(imgL).cuda()
           imgR = torch.FloatTensor(imgR).cuda()     

        imgL, imgR= Variable(imgL), Variable(imgR)

        start_time = time.time()
        with torch.no_grad():
            disp = model(imgL,imgR)
        print('model time = %.2f' %(time.time() - start_time))

        start_time = time.time()
        disp = torch.squeeze(disp)
        print('squeeze time = %.2f' %(time.time() - start_time))
        start_time = time.time()
        pred_disp = disp.data.cpu().numpy()
        print('down time = %.2f' %(time.time() - start_time))

        return pred_disp


def main():
       processed = preprocess.get_transform(augment=False)
       index = -1;

       model.eval()
       while True:
          print("Next image "+ str(index))
          index = index + 1
          if args.isgray:
             imgL_o = cv2.cvtColor(cv2.imread(args.leftimg+str(index).zfill(6)+"_10.png",0), cv2.COLOR_GRAY2RGB)
             imgR_o = cv2.cvtColor(cv2.imread(args.rightimg+str(index).zfill(6)+"_10.png",0), cv2.COLOR_GRAY2RGB)
          else:
             imgL_o = (skimage.io.imread(args.leftimg+str(index).zfill(6)+"_10.png"))
             #.astype('float32'))
             imgR_o = (skimage.io.imread(args.rightimg+str(index).zfill(6)+"_10.png"))
             #.astype('float32'))

          #resize

          scale_percent = 60 # percent of original size
          width = int(imgL_o.shape[1] * scale_percent / 100)
          height = int(imgL_o.shape[0] * scale_percent / 100)
          dim = (width, height)
          #imgL_o = cv2.resize(imgL_o,dim)
          #imgR_o = cv2.resize(imgR_o,dim)
          cv2.imshow('imageLeft',imgL_o)
          cv2.imshow('imgR_o',imgR_o)
          #key = cv2.waitKey(0)

          imgL = processed(imgL_o).numpy()
          imgR = processed(imgR_o).numpy()
          imgL = np.reshape(imgL,[1,3,imgL.shape[1],imgL.shape[2]])
          imgR = np.reshape(imgR,[1,3,imgR.shape[1],imgR.shape[2]])

          # pad to width and hight to 16 times
          if imgL.shape[2] % 16 != 0:
              times = imgL.shape[2]//16       
              top_pad = (times+1)*16 -imgL.shape[2]
          else:
              top_pad = 0
          if imgL.shape[3] % 16 != 0:
              times = imgL.shape[3]//16                       
              left_pad = (times+1)*16-imgL.shape[3]
          else:
              left_pad = 0     
          imgL = np.lib.pad(imgL,((0,0),(0,0),(top_pad,0),(0,left_pad)),mode='constant',constant_values=0)
          imgR = np.lib.pad(imgR,((0,0),(0,0),(top_pad,0),(0,left_pad)),mode='constant',constant_values=0)

          start_time = time.time()
          pred_disp = test(imgL,imgR)
          print('time = %.2f' %(time.time() - start_time))
          if top_pad !=0 or left_pad != 0:
              img = pred_disp[top_pad:,:-left_pad]
          else:
              img = pred_disp
          img = (img*255.0/args.maxdisp).astype('uint8')
          skimage.io.imsave('disparity.png',img)
          #im_color = cv2.applyColorMap(img, cv2.COLORMAP_JET)
          cv2.imshow('depth',img)
          key = cv2.waitKey(0)

          if key == ord('q'):
            print("Exit")
            exit(0)
          #img = np.concatenate((imgL_o, imgR_o),axis=1)
          #img = cv2.line(img, (0, 240), (1504, 240), (0, 0, 255), 2)
          #img = cv2.line(img, (0, 210), (1504, 210), (0, 0, 255), 2)
          #img = cv2.line(img, (0, 270), (1504, 270), (0, 0, 255), 2)
          #skimage.io.imsave('test.png',img)

if __name__ == '__main__':
   main()






