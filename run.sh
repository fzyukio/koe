#!/usr/bin/env bash
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____gnb__by_tsne.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____gnb__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____gnb__by_norm.csv

#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____rf__by_tsne.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____rf__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____rf__by_norm.csv

#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____svm__by_tsne.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____svm__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____svm__by_norm.csv

#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____lda__by_tsne.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____lda__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__lbi____lda__by_norm.csv


#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____gnb__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____gnb__by_norm.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____rf__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=norm --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____rf__by_norm.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____svm__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=norm --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____svm__by_norm.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____lda__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=norm --nfolds=25 --niters=10 --to-csv=csv/marathon__lbi____lda__by_norm.csv


#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____gnb__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____gnb__by_norm.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____rf__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=rf --source=norm --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____rf__by_norm.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____svm__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=svm --source=norm --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____svm__by_norm.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____lda__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-lbi.mat  --classifier=lda --source=norm --nfolds=25 --niters=10 --to-csv=csv/multiple__lbi____lda__by_norm.csv

#--------------------------

#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____gnb__by_tsne.csv
##python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____gnb__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____gnb__by_norm.csv
#
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=tsne --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____rf__by_tsne.csv
##python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____rf__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=norm --nfolds=25 --niters=10 --to-csv=csv/validation__tmi____rf__by_norm.csv
#
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=tsne --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____svm__by_tsne.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=raw --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____svm__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=norm --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____svm__by_norm.csv
#
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=tsne --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____lda__by_tsne.csv
##python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=raw --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____lda__by_raw.csv
#python manage.py run_kfold_validation --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=norm --nfolds=25 --niters=5 --to-csv=csv/validation__tmi____lda__by_norm.csv
#
#
##python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__tmi____gnb__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=5 --to-csv=csv/marathon__tmi____gnb__by_norm.csv
##python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__tmi____rf__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=norm --nfolds=25 --niters=5 --to-csv=csv/marathon__tmi____rf__by_norm.csv
##python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__tmi____svm__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=norm --nfolds=25 --niters=1 --to-csv=csv/marathon__tmi____svm__by_norm.csv
##python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=raw --nfolds=25 --niters=10 --to-csv=csv/marathon__tmi____lda__by_raw.csv
#python manage.py run_kfold_marathon --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=norm --nfolds=25 --niters=1 --to-csv=csv/marathon__tmi____lda__by_norm.csv
#
#
##python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__tmi____gnb__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=5 --to-csv=csv/multiple__tmi____gnb__by_norm.csv
##python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__tmi____rf__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=norm --nfolds=25 --niters=5 --to-csv=csv/multiple__tmi____rf__by_norm.csv
##python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__tmi____svm__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=norm --nfolds=25 --niters=5 --to-csv=csv/multiple__tmi____svm__by_norm.csv
##python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=raw --nfolds=25 --niters=10 --to-csv=csv/multiple__tmi____lda__by_raw.csv
#python manage.py run_kfold_multiple --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=norm --nfolds=25 --niters=5 --to-csv=csv/multiple__tmi____lda__by_norm.csv


#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=tsne --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____gnb__by_tsne.csv
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=gnb --source=norm --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____gnb__by_norm.csv
#
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=tsne --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____rf__by_tsne.csv
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=rf --source=norm --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____rf__by_norm.csv
#
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=tsne --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____svm__by_tsne.csv
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=svm --source=norm --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____svm__by_norm.csv
#
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=tsne --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____lda__by_tsne.csv
#python manage.py find_misclassified_ones --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat  --classifier=lda --source=norm --nfolds=25 --niters=100 --to-csv=csv/misclassified__tmi____lda__by_norm.csv


python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=3
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=4
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=5
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=6
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=7
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=8
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=9
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=10
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=11
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=12
python manage.py run_ndim_tsne_svm --matfile=/Users/yfukuzaw/tmp/bellbird-tmi.mat --classifier=svm --nfolds=25 --niters=10 --ndims=13




