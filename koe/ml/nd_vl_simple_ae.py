

import json
import os
import shutil
import zipfile
from signal import signal, SIGABRT, SIGINT, SIGTERM, SIGUSR1
from uuid import uuid4

import tensorflow as tf
import numpy as np
import time
from tensorboard.compat.tensorflow_stub import dtypes
from tensorflow.contrib.seq2seq import dynamic_decode, TrainingHelper, InferenceHelper, BasicDecoder
from tensorflow.nn import dynamic_rnn, relu

from koe.ml.learning_rate_funcs import lrfunc_classes
from root.utils import mkdirp


tf.logging.set_verbosity(tf.logging.ERROR)
regularizer = tf.contrib.layers.l2_regularizer(scale=0.1)


def make_mlp(input_data, layer_sizes, keep_prob, output_dim):
    out_layer = None
    centre_layer = None

    for index, layer_size in enumerate(layer_sizes):
        if out_layer is None:
            out_layer = tf.layers.dense(input_data, layer_size, activation=tf.nn.sigmoid)
        else:
            out_layer = tf.layers.dense(out_layer, layer_size, activation=tf.nn.sigmoid)
            if index == len(layer_sizes)-1:
                centre_layer = out_layer

    for index, layer_size in enumerate(reversed(layer_sizes)):
        out_layer = tf.layers.dense(out_layer, layer_size, activation=tf.nn.sigmoid)

    out_layer = tf.layers.dense(out_layer, output_dim)
    return out_layer, centre_layer


def extract_saved(tmp_folder, filepath):
    has_saved_checkpoint = False
    with zipfile.ZipFile(filepath, 'r') as zip_file:
        namelist = zip_file.namelist()
        for name in namelist:
            if name == 'checkpoint':
                has_saved_checkpoint = True
            filecontent = zip_file.read(name)
            filepath = os.path.join(tmp_folder, name)
            with open(filepath, 'wb') as f:
                f.write(filecontent)
    return has_saved_checkpoint


class NDSMLPAEFactory:
    def __init__(self):
        self.layer_sizes = []
        self.output_dim = None
        self.input_dim = None
        self.padded_length = None
        self.tmp_folder = None
        self.uuid_code = None
        self.stop_pad_length = 5
        self.stop_pad_token = 0
        self.pad_token = 100
        self.go_token = -100.
        self.keep_prob = None
        self.symmetric = True
        self.lrtype = 'constant'
        self.lrargs = dict(lr=0.001)
        self.write_summary = False
        self._save_to = None

    def set_output(self, filename):
        self._save_to = filename
        if os.path.isfile(filename):
            with zipfile.ZipFile(filename, 'r') as zip_file:
                namelist = zip_file.namelist()
                if 'meta.json' in namelist:
                    meta = json.loads(str(zip_file.read('meta.json'), 'utf-8'))
                    for k, v in list(meta.items()):
                        if not callable(v) and not k.startswith('_'):
                            setattr(self, k, v)

    def build(self):
        if self._save_to is None:
            raise Exception('Must call set_output(_save_to=...) first')

        assert self.lrtype in list(lrfunc_classes.keys())

        if self.uuid_code is None:
            self.uuid_code = uuid4().hex
        if self.tmp_folder is None:
            self.tmp_folder = os.path.join('/tmp', 'NDS2SAE-{}'.format(self.uuid_code))

        if os.path.exists(self.tmp_folder):
            shutil.rmtree(self.tmp_folder)
        mkdirp(self.tmp_folder)

        build_anew = True
        if os.path.isfile(self._save_to):
            has_saved_checkpoint = extract_saved(self.tmp_folder, self._save_to)
            build_anew = not has_saved_checkpoint

        params = {v: k for v, k in list(vars(self).items()) if not callable(k)}
        meta_file = os.path.join(self.tmp_folder, 'meta.json')
        with open(meta_file, 'w') as f:
            json.dump(params, f)

        lrfunc_class = lrfunc_classes[self.lrtype]

        retval = _NDSMLPAE(self)
        retval.learning_rate_func = lrfunc_class(**self.lrargs).get_lr
        retval._save_to = self._save_to
        retval.build_anew = build_anew
        retval.construct()
        return retval


class _NDSMLPAE:
    def __init__(self, factory):
        self.global_step = tf.Variable(0, name='global_step', trainable=False)
        self.input_dim = factory.input_dim
        self.output_dim = factory.output_dim
        self.layer_sizes = factory.layer_sizes
        self.padded_length = factory.padded_length

        self.tmp_folder = factory.tmp_folder
        self.uuid_code = factory.uuid_code
        self.latent_dims = self.layer_sizes[-1]
        self.pad_token = factory.pad_token
        self.go_token = factory.go_token
        self.stop_pad_token = factory.stop_pad_token
        self.stop_pad_length = factory.stop_pad_length
        self.keep_prob = factory.keep_prob
        self.symmetric = factory.symmetric
        self.write_summary = factory.write_summary

        self.input_data = None
        self.output_data = None
        self.start_tokens = None
        self.sequence_length = None
        self.mask = None
        self.target_sequence_length = None
        self.max_target_sequence_length = None
        self.source_sequence_length = None
        self.saved_session_name = None

        self.loss = None
        self.optimizer = None
        self.training_op = None
        self._save_to = None
        self.build_anew = True
        self.train_op = None
        self.enc_state = None
        self.go_tokens = None
        self.training_decoder_output = None
        self.cost = None
        self.inference_decoder_output = None
        self.x_stopping = None
        self.y_stopping = None
        self.predictions = None
        self.learning_rate = None
        self.batch_size = None
        self.target_sequence_length_padded = None
        self.source_sequence_length_padded = None

        def cleanup(*args):
            self.cleanup()

        for sig in (SIGABRT, SIGINT, SIGTERM, SIGUSR1):
            signal(sig, cleanup)

    def cleanup(self):
        if os.path.isdir(self.tmp_folder):
            print(('Cleaned up temp folder {}'.format(self.tmp_folder)))
            shutil.rmtree(self.tmp_folder)

    def copy_saved_to_zip(self):
        save_to_bak = self._save_to + '.bak'
        save_to_bak2 = self._save_to + '.bak2'

        with zipfile.ZipFile(save_to_bak, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
            for root, dirs, files in os.walk(self.tmp_folder):
                for file in files:
                    with open(os.path.join(root, file), 'rb') as f:
                        zip_file.writestr(file, f.read())

        if os.path.isfile(self._save_to):
            os.rename(self._save_to, save_to_bak2)
        os.rename(save_to_bak, self._save_to)
        if os.path.isfile(save_to_bak2):
            os.remove(save_to_bak2)

    def construct(self):
        self.saved_session_name = os.path.join(self.tmp_folder, self.uuid_code)
        self.input_data = tf.placeholder(tf.float32, [None, self.input_dim])
        self.output_data = tf.placeholder(tf.float32, [None, self.input_dim])
        self.learning_rate = tf.placeholder(tf.float32)
        self.batch_size = tf.placeholder(tf.float32)

        self.out, self.enc_state = make_mlp(self.input_data, self.layer_sizes, self.keep_prob, self.output_dim)

    def debug(self, xs, ys):
        self.construct_loss_function()
        saver = tf.train.Saver(max_to_keep=1)
        batch_size = len(xs)
        with tf.Session() as sess:
            init = tf.global_variables_initializer()
            init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))

            X_batch, y_batch, source_sequence_lens, target_sequence_lens, len_mask\
                = self.proprocess_samples(xs, ys)

            actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
            actual_go_tokens = np.full((batch_size, 1, self.output_dim), self.go_token, dtype=np.float32)

            # Training step
            evaled = sess.run(
                [
                    self.train_op,
                    self.cost,
                    self.predictions
                ],
                {
                    self.batch_size: batch_size,
                    self.learning_rate: 0,
                    self.input_data: X_batch,
                    self.output_data: y_batch,
                    self.mask: len_mask,
                    self.start_tokens: actual_start_tokens,
                    self.go_tokens: actual_go_tokens,
                    self.target_sequence_length: target_sequence_lens,
                    self.source_sequence_length: source_sequence_lens
                })
            cost = evaled[1]
            predictions = evaled[2]

            diff = y_batch - predictions
            diff[np.isinf(diff)] = 0
            diff = np.sum(np.square(diff), 2)
            diff *= len_mask

            cross_entropy = np.sum(diff, 1)
            cross_entropy /= (target_sequence_lens + self.stop_pad_length)
            true_cost = np.mean(cross_entropy)

            assert np.allclose(true_cost, cost), 'Cost = {}, tru cost = {}'.format(cost, true_cost)
            print(('Lost = {}'.format(cost)))

    def construct_loss_function(self):
        if self.train_op is None:
            self.predictions = self.out

            # first take square difference. diff_sq.shaeoe = [batch_size, length, output_dim]
            diff = self.output_data - self.predictions
            diff_sq = tf.square(diff)

            # The cost is sum along dimension 2 (output dimension), then dimension 1 (time-axis), then
            # take the mean of the batch
            sum_diff_sq = tf.reduce_sum(diff_sq, axis=1)
            self.cost = tf.reduce_mean(sum_diff_sq)

            # Optimizer
            optimizer = tf.train.AdamOptimizer(self.learning_rate)

            # Gradient Clipping
            gradients = optimizer.compute_gradients(self.cost)
            self.train_op = optimizer.apply_gradients(gradients)
            self.train_op_eob = optimizer.apply_gradients(gradients, global_step=self.global_step)

    @profile  # noqa F821
    def train(self, training_gen, valid_gen, n_iterations=1500, batch_size=50, display_step=1, save_step=100):
        self.construct_loss_function()

        with tf.name_scope('summaries'):
            tf.summary.scalar('learning_rate', self.learning_rate)
            tf.summary.scalar('cost', self.cost)

        saver = tf.train.Saver(max_to_keep=1)
        with tf.Session() as sess:
            # Merge all the summaries and write them out to /tmp/mnist_logs (by default)
            if self.write_summary:
                summary_merged = tf.summary.merge_all()
                train_writer = tf.summary.FileWriter(self.tmp_folder + '/train', graph=sess.graph)
                test_writer = tf.summary.FileWriter(self.tmp_folder + '/test')
            init = tf.global_variables_initializer()
            init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
            current_iteration = self.global_step.eval()
            start_time = int(round(time.time() * 1000))
            start_iteration = current_iteration
            for iteration in range(current_iteration, n_iterations):
                final_batch = False
                current_lr = self.learning_rate_func(global_step=iteration)
                while not final_batch:
                    X_batch, y_batch, final_batch = training_gen(batch_size)
                    actual_batch_size = len(X_batch)

                    # Training step
                    feed_dict = {
                        self.batch_size: actual_batch_size,
                        self.learning_rate: current_lr,
                        self.input_data: X_batch,
                        self.output_data: y_batch
                    }

                    if final_batch:
                        train_op = self.train_op_eob
                    else:
                        train_op = self.train_op

                    if self.write_summary:
                        _, loss, current_lr, summary = \
                            sess.run([train_op, self.cost, self.learning_rate, summary_merged], feed_dict)
                        train_writer.add_summary(summary, iteration)
                    else:
                        _, loss, current_lr = sess.run([train_op, self.cost, self.learning_rate], feed_dict)
                        pass

                # Debug message updating us on the status of the training
                if iteration % display_step == 0 or iteration == n_iterations - 1:
                    xs, ys, _ = valid_gen(batch_size=None)
                    actual_batch_size = len(xs)

                    # Calculate validation cost
                    feed_dict = {
                        self.batch_size: actual_batch_size,
                        self.learning_rate: current_lr,
                        self.input_data: X_batch,
                        self.output_data: y_batch,
                    }

                    if self.write_summary:
                        validation_loss, summary = sess.run([self.cost, summary_merged], feed_dict)
                        test_writer.add_summary(summary, iteration)
                    else:
                        validation_loss = sess.run(self.cost, feed_dict)

                    end_time = int(round(time.time() * 1000))
                    duration = end_time - start_time
                    mean_duration = duration / (iteration - start_iteration)

                    start_time = end_time
                    start_iteration = iteration

                    print(('Ep {:>4}/{} | Losses: {:>7.5f}/{:>7.5f} | LR: {:>6.5f} | Speed: {:>6.1f} ms/Ep'.
                           format(iteration, n_iterations, loss, validation_loss, current_lr, mean_duration)))

                if iteration % save_step == 0 or iteration == n_iterations - 1:
                    start_time_save = int(round(time.time() * 1000))
                    saver.save(sess, self.saved_session_name, global_step=self.global_step)
                    self.copy_saved_to_zip()
                    duration_save = int(round(time.time() * 1000)) - start_time_save
                    print('Saved. Elapsed: {:>6.3f} ms'.format(duration_save))

    def recreate_session(self):
        saver = tf.train.Saver()
        init = tf.global_variables_initializer()
        session = tf.Session()
        session.run(init)
        saver.restore(session, tf.train.latest_checkpoint(self.tmp_folder))
        return session

    def _predict_or_encode(self, mode, test_seq, session=None):
        if mode == 'predict':
            ops = self.out
        else:
            ops = self.enc_state

        max_length = self.padded_length
        batch_size = len(test_seq)
        spects = []

        for i in range(batch_size):

            duration, nfreqbins = test_seq[i].shape
            pad_length = max_length - duration

            pad_value = np.zeros((nfreqbins, pad_length))

            padded_spect = np.concatenate((test_seq[i].transpose(1, 0), pad_value), axis=1)

            # Reshape it to one dimensional
            spects.append(padded_spect.reshape(padded_spect.size))


        X_batch = spects

        feed_dict = {
            self.input_data: X_batch,
        }
        if session is None:
            saver = tf.train.Saver()
            init = tf.global_variables_initializer()
            with tf.Session() as sess:
                init.run()
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
                result = sess.run(ops, feed_dict)
        else:
            result = session.run(ops, feed_dict)

        return result

    def predict(self, test_seq, session=None):
        decoder_output = self._predict_or_encode('predict', test_seq, session)

        restored_output_batch = []
        for index, output in enumerate(decoder_output):
            restored_output = decoder_output[index].reshape(20, self.padded_length)
            duration, nfreqbins = test_seq[index].shape
            restored_output = restored_output[:,:duration]
            restored_output_batch.append(restored_output)

        return restored_output_batch

    def encode(self, test_seq, session=None):
        states = self._predict_or_encode('encode', test_seq, session)
        # return np.concatenate(states, axis=1)
        return states

