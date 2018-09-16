"""
Train a LSTM on audio segments.
"""
import math
import os
import pickle

import numpy as np
import tensorflow as tf
from numpy import random

from django.conf import settings

from koe.rnn_models import DataProvider

num_historical = 5


def dynamicRNN(x, lens, seq_max_len, n_hidden, n_classes):
    # Define weights
    weights = {
        'out': tf.Variable(tf.random_normal([n_hidden, n_classes]), name='weights')
    }
    biases = {
        'out': tf.Variable(tf.random_normal([n_classes]), name='biases')
    }

    # Prepare data shape to match `rnn` function requirements
    # Current data input shape: (batch_size, n_steps, n_input)
    # Required shape: 'n_steps' tensors list of shape (batch_size, n_input)

    # Unstack to get a list of 'n_steps' tensors of shape (batch_size, n_input)
    x = tf.unstack(x, seq_max_len, 1)

    # Define a lstm cell with tensorflow
    lstm_cell = tf.contrib.rnn.BasicLSTMCell(n_hidden)

    # Get lstm cell output, providing 'sequence_length' will perform dynamic
    # calculation.
    outputs, states = tf.contrib.rnn.static_rnn(lstm_cell, x, dtype=tf.float32, sequence_length=lens)

    # When performing dynamic calculation, we must retrieve the last
    # dynamically computed output, i.e., if a sequence length is 10, we need
    # to retrieve the 10th output.
    # However TensorFlow doesn't support advanced indexing yet, so we build
    # a custom op that for each sample in batch size, get its length and
    # get the corresponding relevant output.

    # 'outputs' is a list of output at every timestep, we pack them in a Tensor
    # and change back dimension to [batch_size, n_step, n_input]
    outputs = tf.stack(outputs)
    outputs = tf.transpose(outputs, [1, 0, 2])

    # Hack to build the indexing and retrieve the right output.
    batch_size = tf.shape(outputs)[0]
    # Start indices for each sample
    index = tf.range(0, batch_size) * seq_max_len + (lens - 1)
    # Indexing
    outputs = tf.gather(tf.reshape(outputs, [-1, n_hidden]), index)

    # Linear activation, using outputs computed above
    return tf.matmul(outputs, weights['out']) + biases['out']


def train(dp, eps=0.01, nfolds=10, learning_rate=0.01, resumable=True, name='model'):
    dp.split_folds(nfolds)
    # Parameters
    batch_size = len(dp.data) // nfolds
    display_step = 200

    # Network Parameters
    n_hidden = 10 * dp.input_len  # hidden layer num of features - 10 times the size of inpur

    # tf Graph input
    x = tf.placeholder('float', [None, dp.seq_max_len, dp.input_len], name='x')
    y = tf.placeholder('float', [None, dp.n_classes], name='y')
    # A placeholder for indicating each sequence length
    lens = tf.placeholder(tf.int32, [None], name='lens')

    pred = dynamicRNN(x, lens, dp.seq_max_len, n_hidden, dp.n_classes)

    # Define loss and optimizer
    cost = tf.reduce_mean(tf.nn.softmax_cross_entropy_with_logits(logits=pred, labels=y, name='softmax'), name='rmean')
    optimizer = tf.train.GradientDescentOptimizer(learning_rate=learning_rate).minimize(cost, name='minimise')

    # Evaluate model
    correct_pred = tf.equal(tf.argmax(pred, 1), tf.argmax(y, 1))
    accuracy = tf.reduce_mean(tf.cast(correct_pred, tf.float32))

    # Initialize the variables (i.e. assign their default value)
    init = tf.global_variables_initializer()

    # Add ops to save and restore all the variables.
    saver = tf.train.Saver()

    # Start training
    with tf.Session() as sess:
        for k in range(nfolds):
            backup_filename = os.path.join(settings.BASE_DIR, 'backups/tf/{}-{}.ckpt'.format(name, k))

            backup_index_filename = '{}.index'.format(backup_filename)
            backup_meta_filename = '{}.meta'.format(backup_filename)
            backup_extra_filename = '{}.extra'.format(backup_filename)

            backup_exists = os.path.isfile(backup_index_filename) and\
                            os.path.isfile(backup_meta_filename) and\
                            os.path.isfile(backup_extra_filename)

            if resumable and backup_exists:
                with open(backup_extra_filename, 'rb') as f:
                    extra = pickle.load(f)
                    step = extra['step']
                    accuracies = extra['accuracies']
                    losses = extra['losses']
                    acc_stdev = np.std(accuracies[-num_historical:])
                    loss_stdev = np.std(losses[-num_historical:])
                saver.restore(sess, backup_filename)
            else:
                sess.run(init)
                acc_stdev = math.inf
                loss_stdev = math.inf
                step = 0
                accuracies = []
                losses = []

            trainableset, validset = dp.get_fold(k)

            while acc_stdev > eps or loss_stdev > eps:
                step += 1
                trainset, testset = trainableset.split(nfolds - 1)

                tr_batch_x, tr_batch_y, tr_batch_lens = trainset.next(batch_size)

                # Run optimization op (backprop)
                sess.run(optimizer, feed_dict={
                    x: tr_batch_x, y: tr_batch_y,
                    lens: tr_batch_lens
                })
                if step % display_step == 0 or step == 1:
                    ts_batch_x, ts_batch_y, ts_batch_lens = testset.all()
                    # Calculate batch accuracy & loss
                    acc, loss = sess.run([accuracy, cost],
                                         feed_dict={x: ts_batch_x, y: ts_batch_y, lens: ts_batch_lens})

                    accuracies.append(acc)
                    losses.append(loss)
                    if len(accuracies) >= num_historical:
                        acc_stdev = np.std(accuracies[-num_historical:])
                        loss_stdev = np.std(losses[-num_historical:])

                    print('\tFold {}, Step {}, Loss={:.6f}|{:.6f}, Accuracy={:.5f}|{:.5f}'
                          .format(k + 1, step, loss, loss_stdev, acc, acc_stdev))
                    if resumable:
                        saver.save(sess, backup_filename)
                        with open(backup_extra_filename, 'wb') as f:
                            pickle.dump(dict(losses=losses, accuracies=accuracies, step=step), f)

            # Calculate accuracy
            vl_data = validset.data
            vl_label = validset.labels
            vl_lens = validset.lens
            vl_accuracy = sess.run(accuracy, feed_dict={x: vl_data, y: vl_label, lens: vl_lens})
            print('Fold {}, Valid Accuracy: {}'.format(k + 1, vl_accuracy))


def generate_sequences(n_samples=1000, max_seq_len=20, min_seq_len=3, max_value=1000, shape1=1):
    """
    Create a dataset of dynamic length sequences. Two kinds of sequences are generated:
     1. Linear: random start, but continuous thereafter, e.g. [6,7,8,9]; [10, 11, 12, 13, 14, 15]
     2. Random:  random numbers
    The sequences can be two dimensional, row-based
    :param n_samples: number of sequences
    :param max_seq_len: max length
    :param min_seq_len: min length
    :param max_value: max value of any data point
    :param shape1: size of the second dimension
    :return: list of sequences and their respective labels, e.g. ['linear', 'random', 'random', 'linear', ...]
    """
    data = []
    labels = []
    for i in range(n_samples):
        # Random sequence length
        length = random.randint(min_seq_len, max_seq_len)
        # Add a random or linear int sequence (50% prob)
        s = []
        if random.random() < .5:
            # Generate a linear sequence
            label = 'linear'
            for i in range(shape1):
                rand_start = random.randint(0, max_value - length)
                s_ = np.arange(rand_start, rand_start + length).reshape((length, 1))
                s.append(s_)
        else:
            # Generate a random sequence
            label = 'random'
            for i in range(shape1):
                s_ = random.randint(0, max_value, size=length).reshape((length, 1))
                s.append(s_)
        data.append(np.hstack(s))
        labels.append(label)
    return data, labels


if __name__ == '__main__':
    data, labels = generate_sequences(n_samples=1500, max_seq_len=20, min_seq_len=3, max_value=1000, shape1=1)
    data_provider = DataProvider(data, labels)
    train(data_provider, nfolds=10, name='toy5')
