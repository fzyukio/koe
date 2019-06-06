"""
Implement a nd (multi-dimensional), vl (variable length) s2s (sequence to sequence) auto-encoder
"""
import json
import os
import shutil
import zipfile
from uuid import uuid4

import numpy as np
import tensorflow as tf
from tensorboard.compat.tensorflow_stub import dtypes

from root.utils import mkdirp


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


def make_cell(layer_sizes):
    cells = []
    for layer_size in layer_sizes:
        cell = tf.contrib.rnn.GRUCell(layer_size,
                                      bias_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
                                      kernel_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
                                      activation=tf.nn.relu)
        cells.append(cell)
    return tf.contrib.rnn.MultiRNNCell(cells)


class NDS2SAEFactory:
    def __init__(self):
        self.layer_sizes = []
        self.output_dim = 1
        self.input_dim = 1
        self.max_seq_len = 30
        self.learning_rate = 0.001
        self.tmp_folder = None
        self.uuid_code = None
        self.go_token = -1.
        self.pad_token = 0

    def build(self, save_to):
        if os.path.isfile(save_to):
            with zipfile.ZipFile(save_to, 'r') as zip_file:
                namelist = zip_file.namelist()
                if 'meta.json' in namelist:
                    meta = json.loads(zip_file.read('meta.json'))
                    for k, v in meta.items():
                        setattr(self, k, v)

        if self.uuid_code is None:
            self.uuid_code = uuid4().hex
        if self.tmp_folder is None:
            self.tmp_folder = os.path.join('/tmp', 'NDS2SAE-{}'.format(self.uuid_code))

        if os.path.exists(self.tmp_folder):
            shutil.rmtree(self.tmp_folder)
        mkdirp(self.tmp_folder)

        build_anew = True
        if os.path.isfile(save_to):
            has_saved_checkpoint = extract_saved(self.tmp_folder, save_to)
            build_anew = not has_saved_checkpoint

        params = vars(self)
        meta_file = os.path.join(self.tmp_folder, 'meta.json')
        with open(meta_file, 'w') as f:
            json.dump(params, f)

        retval = _NDS2SAE(self)
        retval.save_to = save_to
        retval.build_anew = build_anew
        retval.construct()
        return retval


class _NDS2SAE:
    def __init__(self, factory):
        self.global_step = tf.Variable(0, name='global_step', trainable=False)
        self.learning_rate = factory.learning_rate
        self.max_seq_len = factory.max_seq_len
        self.input_dim = factory.input_dim
        self.output_dim = factory.output_dim
        self.layer_sizes = factory.layer_sizes
        self.learning_rate = factory.learning_rate
        self.tmp_folder = factory.tmp_folder
        self.uuid_code = factory.uuid_code
        self.latent_dims = sum(self.layer_sizes)
        self.go_token = factory.go_token

        self.input_data = None
        self.output_data = None
        self.start_tokens = None
        self.sequence_length = None
        self.mask = None
        self.target_sequence_length = None
        self.max_target_sequence_length = None
        self.source_sequence_length = None
        self.saved_session_name = None

        self.outputs = None
        self.states = None
        self.loss = None
        self.optimizer = None
        self.training_op = None
        self.save_to = None
        self.build_anew = True

    def cleanup(self):
        shutil.rmtree(self.tmp_folder)

    def copy_saved_to_zip(self):
        save_to_bak = self.save_to + '.bak'
        save_to_bak2 = self.save_to + '.bak2'

        with zipfile.ZipFile(save_to_bak, 'w', zipfile.ZIP_BZIP2, False) as zip_file:
            for root, dirs, files in os.walk(self.tmp_folder):
                for file in files:
                    with open(os.path.join(root, file), 'rb') as f:
                        zip_file.writestr(file, f.read())

        if os.path.isfile(self.save_to):
            os.rename(self.save_to, save_to_bak2)
        os.rename(save_to_bak, self.save_to)
        if os.path.isfile(save_to_bak2):
            os.remove(save_to_bak2)

    def construct(self):
        self.saved_session_name = os.path.join(self.tmp_folder, self.uuid_code)
        self.input_data = tf.placeholder(tf.float32, [None, None, self.input_dim])
        self.output_data = tf.placeholder(tf.float32, [None, None, self.output_dim])
        self.start_tokens = tf.placeholder(tf.float32, [None, self.output_dim])
        self.go_tokens = tf.placeholder(tf.float32, [None, 1, self.output_dim])
        self.sequence_length = tf.placeholder(tf.int32, [None])
        self.mask = tf.placeholder(tf.float32, [None, None])
        self.target_sequence_length = tf.placeholder(tf.int32, (None,), name='target_sequence_length')
        self.max_target_sequence_length = tf.reduce_max(self.target_sequence_length, name='max_target_len')
        self.source_sequence_length = tf.placeholder(tf.int32, (None,), name='source_sequence_length')

        self.enc_cell = make_cell(self.layer_sizes)

        _, self.enc_state = tf.nn.dynamic_rnn(self.enc_cell, self.input_data,
                                              sequence_length=self.source_sequence_length,
                                              dtype=tf.float32)

        self.dec_cell = make_cell(self.layer_sizes)

        # 3. Dense layer to translate the decoder's output at each time
        # step into a choice from the target vocabulary
        self.projection_layer = tf.layers.Dense(units=self.output_dim,
                                                kernel_initializer=tf.truncated_normal_initializer(mean=0.0,
                                                                                                   stddev=0.1))

        # 4. Set up a training decoder and an inference decoder
        # Training Decoder
        self.training_decoder_output = None
        with tf.variable_scope("decode"):
            # During PREDICT mode, the output data is none so we can't have a training
            # model.
            # Helper for the training process. Used by BasicDecoder to read inputs.

            dec_input = tf.concat([self.go_tokens, self.output_data], 1)
            training_helper = tf.contrib.seq2seq.TrainingHelper(inputs=dec_input,
                                                                sequence_length=self.target_sequence_length,
                                                                time_major=False)

            # Basic decoder
            training_decoder = tf.contrib.seq2seq.BasicDecoder(self.dec_cell,
                                                               training_helper,
                                                               self.enc_state,
                                                               self.projection_layer)

            # Perform dynamic decoding using the decoder
            self.training_decoder_output = tf.contrib.seq2seq.dynamic_decode(
                training_decoder, impute_finished=True, maximum_iterations=self.max_target_sequence_length)[0]
        # 5. Inference Decoder
        # Reuses the same parameters trained by the training process
        with tf.variable_scope("decode", reuse=True):
            inference_helper = tf.contrib.seq2seq.InferenceHelper(
                sample_fn=lambda x: x,
                sample_shape=[self.output_dim],
                sample_dtype=dtypes.float32,
                start_inputs=self.start_tokens,
                end_fn=lambda sample_ids: False
            )

            # Basic decoder
            inference_decoder = tf.contrib.seq2seq.BasicDecoder(self.dec_cell,
                                                                inference_helper,
                                                                self.enc_state,
                                                                self.projection_layer)

            # Perform dynamic decoding using the decoder
            self.inference_decoder_output = tf.contrib.seq2seq.dynamic_decode(
                inference_decoder,
                impute_finished=True,
                maximum_iterations=self.max_target_sequence_length)[0]

        predictions = self.training_decoder_output.rnn_output
        diff = tf.reduce_sum(tf.square(self.output_data[:, :self.max_target_sequence_length, :] - predictions), 2)
        diff *= self.mask[:, :self.max_target_sequence_length]

        cross_entropy = tf.reduce_sum(diff, 1)
        cross_entropy /= tf.reduce_sum(self.mask, 1)
        self.cost = tf.reduce_mean(cross_entropy)

        # Optimizer
        optimizer = tf.train.AdamOptimizer(self.learning_rate)

        # Gradient Clipping
        gradients = optimizer.compute_gradients(self.cost)
        capped_gradients = [(tf.clip_by_value(grad, -5., 5.), var) for grad, var in gradients if grad is not None]
        self.train_op = optimizer.apply_gradients(capped_gradients, global_step=self.global_step)

    def train(self, training_gen, valid_gen, n_iterations=1500, batch_size=50, display_step=20):
        saver = tf.train.Saver(max_to_keep=1)
        with tf.Session() as sess:
            init = tf.global_variables_initializer()
            init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
            current_iteration = self.global_step.eval()
            for iteration in range(current_iteration, n_iterations):

                X_batch, y_batch, sequence_lens, len_mask = training_gen(batch_size)
                actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
                actual_go_tokens = np.full((batch_size, 1, self.output_dim), self.go_token, dtype=np.float32)

                feed_dict = {
                    self.input_data: X_batch,
                    self.output_data: y_batch,
                    self.mask: len_mask,
                    self.start_tokens: actual_start_tokens,
                    self.go_tokens: actual_go_tokens,
                    self.target_sequence_length: sequence_lens,
                    self.source_sequence_length: sequence_lens
                }

                # Training step
                _, loss = sess.run([self.train_op, self.cost], feed_dict)

                # Debug message updating us on the status of the training
                if iteration % display_step == 0 and iteration > 0:
                    X_batch, y_batch, sequence_lens, len_mask = valid_gen(batch_size)
                    actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
                    actual_go_tokens = np.full((batch_size, 1, self.output_dim), self.go_token, dtype=np.float32)

                    feed_dict = {
                        self.input_data: X_batch,
                        self.output_data: y_batch,
                        self.mask: len_mask,
                        self.start_tokens: actual_start_tokens,
                        self.go_tokens: actual_go_tokens,
                        self.target_sequence_length: sequence_lens,
                        self.source_sequence_length: sequence_lens
                    }

                    # Calculate validation cost
                    validation_loss = sess.run(self.cost, feed_dict)

                    print('Epoch {:>3}/{} - Loss: {:>6.3f}  - Validation loss: {:>6.3f}'
                          .format(iteration, n_iterations, loss, validation_loss))

                    saver.save(sess, self.saved_session_name, global_step=self.global_step)
                    self.copy_saved_to_zip()

    def recreate_session(self):
        saver = tf.train.Saver()
        init = tf.global_variables_initializer()
        session = tf.Session()
        session.run(init)
        saver.restore(session, tf.train.latest_checkpoint(self.tmp_folder))
        return session

    def _predict_or_encode(self, mode, test_seq, test_seq_len, len_mask, session=None):
        if mode == 'predict':
            ops = self.inference_decoder_output
        else:
            ops = self.enc_state

        batch_size = len(test_seq)
        actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
        feed_dict = {
            self.input_data: test_seq,
            self.mask: len_mask,
            self.start_tokens: actual_start_tokens,
            self.target_sequence_length: [self.max_seq_len],
            self.source_sequence_length: test_seq_len
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

    def predict(self, test_seq, test_seq_len, len_mask, session=None):
        decoder_output = self._predict_or_encode('predict', test_seq, test_seq_len, len_mask, session)
        return decoder_output.rnn_output

    def encode(self, test_seq, test_seq_len, len_mask, session=None):
        states = self._predict_or_encode('encode', test_seq, test_seq_len, len_mask, session)
        return np.concatenate(states, axis=1)
