import os
import gzip
import time
from urllib.request import urlretrieve

from django.core.management import BaseCommand
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from ggplot import *
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE


IMAGE_SIZE = 28
NUM_CHANNELS = 1
PIXEL_DEPTH = 255
NUM_LABELS = 10


SOURCE_URL = 'https://storage.googleapis.com/cvdf-datasets/mnist/'
WORK_DIRECTORY = "/tmp/mnist-data"


def maybe_download(filename):
    """A helper to download the data files if not present."""
    if not os.path.exists(WORK_DIRECTORY):
        os.mkdir(WORK_DIRECTORY)
    filepath = os.path.join(WORK_DIRECTORY, filename)
    if not os.path.exists(filepath):
        filepath, _ = urlretrieve(SOURCE_URL + filename, filepath)
        statinfo = os.stat(filepath)
        print('Successfully downloaded', filename, statinfo.st_size, 'bytes.')
    else:
        print('Already downloaded', filename)
    return filepath


def extract_data(filename, num_images):
    """
    Extract the images into a 4D tensor [image index, y, x, channels].
    Values are rescaled from [0, 255] down to [-0.5, 0.5].
    """
    with gzip.open(filename) as bytestream:
        bytestream.read(16)
        buf = bytestream.read(IMAGE_SIZE * IMAGE_SIZE * num_images)
        data = np.frombuffer(buf, dtype=np.uint8).astype(np.float32)
        # data = (data - (PIXEL_DEPTH / 2.0)) / PIXEL_DEPTH
        data = data.reshape(num_images, IMAGE_SIZE * IMAGE_SIZE)
        return data


def extract_labels(filename, num_images):
    """
    Extract the labels into a vector of int64 label IDs.
    """
    with gzip.open(filename) as bytestream:
        bytestream.read(8)
        buf = bytestream.read(1 * num_images)
        labels = np.frombuffer(buf, dtype=np.uint8).astype(np.int64)
    return labels


class Command(BaseCommand):
    def handle(self, *args, **options):
        train_data_filename = maybe_download('train-images-idx3-ubyte.gz')
        train_labels_filename = maybe_download('train-labels-idx1-ubyte.gz')
        test_data_filename = maybe_download('t10k-images-idx3-ubyte.gz')
        test_labels_filename = maybe_download('t10k-labels-idx1-ubyte.gz')

        train_data = extract_data(train_data_filename, 60000)
        train_labels = extract_labels(train_labels_filename, 60000)
        test_data = extract_data(test_data_filename, 10000)
        test_labels = extract_labels(test_labels_filename, 10000)

        X = np.concatenate((train_data, test_data))
        y = np.concatenate((train_labels, test_labels))

        feat_cols = ['pixel' + str(i) for i in range(X.shape[1])]

        df = pd.DataFrame(X, columns=feat_cols)
        df['label'] = y
        df['label'] = df['label'].apply(lambda i: str(i))

        rndperm = np.random.permutation(df.shape[0])

        pca_50 = PCA(n_components=50)
        pca_result_50 = pca_50.fit_transform(df[feat_cols].values)
        print('Cumulative explained variation for 50 principal components: {}'.format(
            np.sum(pca_50.explained_variance_ratio_)))

        n_sne = 10000

        time_start = time.time()

        tsne = TSNE(n_components=2, verbose=1, perplexity=40, n_iter=300)
        tsne_pca_results = tsne.fit_transform(pca_result_50[rndperm[:n_sne]])

        print('t-SNE done! Time elapsed: {} seconds'.format(time.time() - time_start))

        df_tsne = df.loc[rndperm[:n_sne], :].copy()
        df_tsne['x-tsne-pca'] = tsne_pca_results[:, 0]
        df_tsne['y-tsne-pca'] = tsne_pca_results[:, 1]

        chart = ggplot(df_tsne, aes(x='x-tsne-pca', y='y-tsne-pca', color='label')) \
                + geom_point(size=70, alpha=0.1) \
                + ggtitle("tSNE dimensions colored by Digit (PCA)")
        chart.show()

        pca = PCA(n_components=3)
        pca_result = pca.fit_transform(df[feat_cols].values)

        df['pca-one'] = pca_result[:, 0]
        df['pca-two'] = pca_result[:, 1]
        df['pca-three'] = pca_result[:, 2]

        print('Explained variation per principal component: {}'.format(pca.explained_variance_ratio_))

        chart = ggplot(df.loc[rndperm[:3000], :], aes(x='pca-one', y='pca-two', color='label')) \
                + geom_point(size=75, alpha=0.8) \
                + ggtitle("First and Second Principal Components colored by digit")
        chart.show()


        # Plot the graph
        fig = plt.figure(figsize=(16, 7))
        for i in range(0, 30):
            ax = fig.add_subplot(3, 10, i + 1, title='Digit: ' + str(df.loc[rndperm[i], 'label']))
            ax.matshow(df.loc[rndperm[i], feat_cols].values.reshape((28, 28)).astype(float))

        plt.show()


