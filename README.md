## 使い方
python main.py

##設定
config.iniにそれぞれの設定を記述

- [placedim] : 画像の中でどの部分に数字のディスプレイがあるか
- [numdim] : 数字の高さと幅
- [figurenum] : LED点灯とみなすための範囲と割合の閾値
- [figure1] : 1を認識するための設定(numdimに近い)
- [folder] : 素材画像などの場所

##結果
以下の情報のcsvになる
- 時刻,素材画像名,結果

