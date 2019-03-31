from imutils.perspective import four_point_transform
from imutils import contours
import imutils
import glob
import imutils
import cv2
import time
import csv
from datetime import datetime
import traceback
import sys
import argparse
import configparser
import os

#define the dictionary of digit segments so we can identify
# each digit on the thermostat
DIGITS_LOOKUP = {
	(1, 1, 1, 0, 1, 1, 1): 0,
	(0, 0, 1, 0, 0, 1, 0): 1,
	(1, 0, 1, 1, 1, 0, 1): 2,
	(1, 0, 1, 1, 0, 1, 1): 3,
	(0, 1, 1, 1, 0, 1, 0): 4,
	(1, 1, 0, 1, 0, 1, 1): 5,
	(1, 1, 0, 1, 1, 1, 1): 6,
	(1, 0, 1, 0, 0, 1, 0): 7,
	(1, 1, 1, 1, 1, 1, 1): 8,
	(1, 1, 1, 1, 0, 1, 1): 9
}

#画像にエッジ補正をかける
#どの位置に注目して行うかを引数で渡す。
#defaultとしてもらった画像の位置を利用する

def makedgedimg(image,dimx1,dimx2,dimy1,dimy2):		
    image = imutils.resize(image,height=500)
    image = image[int(dimx1):int(dimx2),int(dimy1):int(dimy2)]
		#グレースケールへ変換
    gray = cv2.cvtColor(image,cv2.COLOR_BGR2GRAY)
    #5*5のマスでガウシアンフィルタをかけることで画像が平滑化(noise除去)
    blurred = cv2.GaussianBlur(gray, (5,5),0)
    #キャニー法によりエッジ抽出 第一閾値、第二閾値　第4引数は画像の勾配を計算するためのSobelフィルタのサイズ aperture_size で，デフォルト値は3
    edged = cv2.Canny(blurred,50,100,255)
    #plt.imshow(edged)
    return image,gray,edged

def getCnt(edged):
    #輪郭抽出 入力・contour retrieval mode・輪郭検出方
    #輪郭とは同じ色や値を持つ(境界線に沿った)連続する点をつなげて形成される曲線のことです
    cnts = cv2.findContours(edged.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    #findContoursの中から必要な情報を抜き出す
    cnts = imutils.grab_contours(cnts)
    cnts = sorted(cnts, key=cv2.contourArea, reverse=True)
    displayCnt = None

    # loop over the contours
    for c in cnts:
        # 周囲長さを取得 Trueなら輪郭は閉じている
        peri = cv2.arcLength(c, True)
        # 無駄のない輪郭線へ修正
        approx = cv2.approxPolyDP(c, 0.02 * peri, True)
 
        # if the contour has four vertices, then we have found
        # the thermostat display
        if len(approx) == 4:
            displayCnt = approx
            break
            
    return displayCnt

def affine(displayCnt):
		try :
				# extract the thermostat display, apply a perspective transform
				# to it　　4点抽出
				warped = four_point_transform(gray, displayCnt.reshape(4, 2))
				output = four_point_transform(image, displayCnt.reshape(4, 2))
				
				return warped,output
		except:
				traceback.print_exc()

def colorConvert(warped):
    # threshold the warped image, then apply a series of morphological
    # operations to cleanup the thresholded image
    thresh = cv2.threshold(warped, 0, 255,cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (1, 5))
    thresh = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)
    thresh = cv2.bitwise_not(thresh)

    return thresh


#数値の部分のみの輪郭を抽出してその座標を取得する
#数値かどうかの判断としてそのwやhのサイズを利用しているので
#ここをパラメータとして渡す

def getNumberCnt(thresh,numberw,numberhmin,numberhmax):
    # find contours in the thresholded image, then initialize the
    # digit contours lists
    cnts = cv2.findContours(thresh.copy(), cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    #cntsは輪郭だから
    cnts = imutils.grab_contours(cnts)
    digitCnts = []
 
    # loop over the digit area candidates
    px,py,pw,ph=0,0,0,0

    for c in cnts:
        # compute the bounding box of the contour
        (x, y, w, h) = cv2.boundingRect(c)
        #はじは取り除く
        # if the contour is sufficiently large, it must be a digit
        if w >= int(numberw) and (h >= int(numberhmin) and h <= int(numberhmax)):
            digitCnts.append(c)
            cv2.rectangle(output, (x, y), (x+w, y+h), (0, 0, 255), 1)
            print(x,y,w,h)
            (px,py,pw,ph) = (x,y,w,h)

    print(len(digitCnts))
    return digitCnts

#変数1. 数値であると判断するための切り取り方
#変数2  LED点灯と判断するための面積的なthrethold 
#変数3.「1」の認識のため、wが極端に小さい場合には1となる

def defineNumber(digitCnts,dW_,dH_,dHC_,threthold,wmin1,wmax1):
		# sort the contours from left-to-right, then initialize the
    # actual digits themselves
    #左から数字を読み込む
    digitCnts = contours.sort_contours(digitCnts,
        method="left-to-right")[0]
    digits = []

    # loop over each of the digits
    for c in digitCnts:
        # extract the digit ROI
        (x, y, w, h) = cv2.boundingRect(c)
        #画像を切り出し
        roi = thresh[y:y + h, x:x + w]
 
        # compute the width and height of each of the 7 segments
        # we are going to examine
        (roiH, roiW) = roi.shape
        (dW, dH) = (int(roiW * float(dW_)), int(roiH * float(dH_)))
        #dW__ = roiW * float(dW_)
        #dH__ = roiH * float(dH_)
        #dHC__ = roiH * float(dHC_)
        #(dW, dH) = (int(dW_), int(dH_))
        dHC = int(roiH * float(dHC_))
        #dHC = int(dHC__)

        # define the set of 7 segments
        segments = [
            ((0, 0), (w, dH)),	# top
            ((0, 0), (dW, h // 2)),	# top-left
            ((w - dW, 0), (w, h // 2)),	# top-right
            ((0, (h // 2) - dHC) , (w, (h // 2) + dHC)), # center
            ((0, h // 2), (dW, h)),	# bottom-left
            ((w - dW, h // 2), (w, h)),	# bottom-right
            ((0, h - dH), (w, h))	# bottom
        ]
        on = [0] * len(segments)

        # loop over the segments
        for (i, ((xA, yA), (xB, yB))) in enumerate(segments):
            # extract the segment ROI, count the total number of
            # thresholded pixels in the segment, and then compute
            # the area of the segment
            segROI = roi[yA:yB, xA:xB]
            total = cv2.countNonZero(segROI)
            area = (xB - xA) * (yB - yA)
 
            # if the total number of non-zero pixels is greater than
            # 50% of the area, mark the segment as "on"
            if total / float(area) > float(threthold):
            #if total / float(area) > 0.3:
                on[i]= 1
 
        # lookup the digit and draw it on the image
        try:
           #try:
            if (w >= int(wmin1) and w < int(wmax1)):
                digit = 1
            else :
                digit = DIGITS_LOOKUP[tuple(on)]
        except:
            digit = 0 
            
            
        digits.append(digit)
        cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 1)
        cv2.putText(output, str(digit), (x - 10, y - 10),
        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (0, 255, 0), 2)

    print(digits)
    return digits
    


if __name__ == '__main__':
		# 引数でディレクトリ追加
		# 引数でパラメータ追加	

    args= sys.argv
    inifile = configparser.ConfigParser()
    inifile.read('./config.ini', 'UTF-8')
    dimx1 = inifile.get('placedim', 'dimx1')
    dimx2 = inifile.get('placedim', 'dimx2')
    dimy1 = inifile.get('placedim', 'dimy1')
    dimy2 = inifile.get('placedim', 'dimy2')
    numberw = inifile.get('numdim', 'numberw')
    numberhmin =inifile.get('numdim', 'numberhmin')
    numberhmax =inifile.get('numdim', 'numberhmax')
    dW = inifile.get('figurenum', 'dW')
    dH = inifile.get('figurenum', 'dH')
    dHC = inifile.get('figurenum', 'dHC')
    threthold = inifile.get('figurenum', 'threthold')
    wmin1 = inifile.get('figure1', '1wmin')
    wmax1 = inifile.get('figure1', '1wmax')
    img_path = inifile.get('folder', 'img_path')
    csv_name = inifile.get('folder', 'result_name')

    files = glob.glob(img_path)

    with open(csv_name,"w") as f:
        writer = csv.writer(f, lineterminator='\n') # 改行コード（\n）を指定しておく
        for file in files:
            try:
                image = cv2.imread(file)
                image,gray,edged = makedgedimg(image,dimx1,dimx2,dimy1,dimy2)
                displayCnt = getCnt(edged)
                warped,output = affine(displayCnt)
                thresh = colorConvert(warped)
                digitCnts = getNumberCnt(thresh,numberw,numberhmin,numberhmax)
                digits = defineNumber(digitCnts,dW,dH,dHC,threthold,wmin1,wmax1)
                print(file)
                print(digits)
                appendlist = []
                appendlist.append(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
                appendlist.append(os.path.basename(file))
                appendlist.append(''.join(map(str,digits)))
                writer.writerow(appendlist)
                time.sleep(0.1)
            except:
                print("cant read data")
                appendlist.append(datetime.now().strftime("%Y/%m/%d %H:%M:%S"))
                appendlist.append(os.path.basename(file))
                appendlist.append("")
                writer.writerow(appendlist)
                time.sleep(0.1)
