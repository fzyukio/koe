import json
import os
import shutil
import zipfile
from signal import signal, SIGABRT, SIGINT, SIGTERM, SIGUSR1
from uuid import uuid4

import tensorflow as tf
import numpy as np
from tensorboard.compat.tensorflow_stub import dtypes
from tensorflow.contrib.seq2seq import dynamic_decode, TrainingHelper, InferenceHelper, BasicDecoder
from tensorflow.nn import dynamic_rnn, relu
from root.utils import mkdirp


def make_cell(layer_sizes, keep_prob=None):
    cells = []
    for layer_size in layer_sizes:
        cell = tf.contrib.rnn.GRUCell(layer_size,
                                      bias_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
                                      kernel_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
                                      activation=relu)
        cells.append(cell)

    lstm = tf.contrib.rnn.MultiRNNCell(cells)
    if keep_prob:
        return tf.contrib.rnn.DropoutWrapper(lstm, input_keep_prob=keep_prob)
    else:
        return lstm


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


class NDS2SAEFactory:
    def __init__(self):
        self.layer_sizes = []
        self.output_dim = 1
        self.input_dim = 1
        self.learning_rate = 0.01
        self.tmp_folder = None
        self.uuid_code = None
        self.stop_pad_length = 5
        self.stop_pad_token = 0
        self.pad_token = 100
        self.go_token = -100.
        self.keep_prob = 1
        self.symmetric = True

    def build(self, save_to):
        if os.path.isfile(save_to):
            with zipfile.ZipFile(save_to, 'r') as zip_file:
                namelist = zip_file.namelist()
                if 'meta.json' in namelist:
                    meta = json.loads(zip_file.read('meta.json'))
                    for k, v in list(meta.items()):
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
        self.input_dim = factory.input_dim
        self.output_dim = factory.output_dim
        self.layer_sizes = factory.layer_sizes
        self.starter_learning_rate = factory.learning_rate
        self.tmp_folder = factory.tmp_folder
        self.uuid_code = factory.uuid_code
        self.latent_dims = sum(self.layer_sizes)
        self.pad_token = factory.pad_token
        self.go_token = factory.go_token
        self.stop_pad_token = factory.stop_pad_token
        self.stop_pad_length = factory.stop_pad_length
        self.keep_prob = factory.keep_prob
        self.symmetric = factory.symmetric

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
        self.save_to = None
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

        def cleanup(*args):
            self.cleanup()

        for sig in (SIGABRT, SIGINT, SIGTERM, SIGUSR1):
            signal(sig, cleanup)

    def cleanup(self):
        if os.path.isdir(self.tmp_folder):
            print(('Cleaned up temp folder {}'.format(self.tmp_folder)))
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
        self.x_stopping = np.full((self.stop_pad_length, self.input_dim), self.stop_pad_token, dtype=np.float32)
        self.y_stopping = np.full((self.stop_pad_length, self.output_dim), self.stop_pad_token, dtype=np.float32)
        self.learning_rate = tf.train.exponential_decay(self.starter_learning_rate, self.global_step, 100000, 0.96,
                                                        staircase=True)

        enc_cell = make_cell(self.layer_sizes, self.keep_prob)

        # We want to train the decoder to learn the stopping point as well,
        # so the sequence lengths is extended for both the decoder and the encoder
        # logic: the encoder will learn that the stopping token is the signal that the input is finished
        #        the decoder will learn to produce the stopping token to match the expected output
        #        the inferer will learn to produce the stopping token for us to recognise that and stop inferring
        source_sequence_length_padded = self.source_sequence_length + self.stop_pad_length
        target_sequence_length_padded = self.target_sequence_length + self.stop_pad_length
        max_target_sequence_length_padded = self.max_target_sequence_length + self.stop_pad_length

        _, self.enc_state = dynamic_rnn(enc_cell, self.input_data, sequence_length=source_sequence_length_padded,
                                        dtype=tf.float32, time_major=False)
        if self.symmetric:
            self.enc_state = self.enc_state[::-1]
            dec_cell = make_cell(self.layer_sizes[::-1], self.keep_prob)
        else:
            dec_cell = make_cell(self.layer_sizes, self.keep_prob)

        # 3. Dense layer to translate the decoder's output at each time
        # step into a choice from the target vocabulary
        projection_layer = tf.layers.Dense(units=self.output_dim,
                                           kernel_initializer=tf.truncated_normal_initializer(mean=0.0, stddev=0.1))

        # 4. Set up a training decoder and an inference decoder
        # Training Decoder
        with tf.variable_scope("decode"):
            # During PREDICT mode, the output data is none so we can't have a training model.
            # Helper for the training process. Used by BasicDecoder to read inputs.
            dec_input = tf.concat([self.go_tokens, self.output_data], 1)
            training_helper = TrainingHelper(inputs=dec_input,
                                             sequence_length=target_sequence_length_padded,
                                             time_major=False)

            # Basic decoder
            training_decoder = BasicDecoder(dec_cell, training_helper, self.enc_state, projection_layer)

            # Perform dynamic decoding using the decoder
            self.training_decoder_output\
                = dynamic_decode(training_decoder,
                                 # True because we're using variable length sequences, which have finish points
                                 impute_finished=True,
                                 maximum_iterations=max_target_sequence_length_padded)[0]
        # 5. Inference Decoder
        # Reuses the same parameters trained by the training process
        with tf.variable_scope("decode", reuse=True):
            def end_fn(time_step_value):
                # Ideally, the inferer should produce the stopping token
                # Which can be assessed as being equal to the modelled stop token, and this should be return:
                # return tf.reduce_all(tf.equal(time_step_value, self.y_stopping))

                # However due to the nature of training, the produced stop token will never be exactly the same
                # as the modelled one. If we use an embedded layer, then this top token can be learned
                # however as we are not using the embedded layer, this function should return False
                # meaning there is no early stop
                return False

            inference_helper = InferenceHelper(
                sample_fn=lambda x: x,
                sample_shape=[self.output_dim],
                sample_dtype=dtypes.float32,
                start_inputs=self.start_tokens,
                end_fn=end_fn
            )

            # Basic decoder
            inference_decoder = BasicDecoder(dec_cell, inference_helper, self.enc_state, projection_layer)

            # Perform dynamic decoding using the decoder
            self.inference_decoder_output = dynamic_decode(
                inference_decoder,
                # True because we're using variable length sequences, which have finish points
                impute_finished=True,
                maximum_iterations=max_target_sequence_length_padded)[0]

        self.predictions = self.training_decoder_output.rnn_output
        diff = self.output_data - self.predictions
        diff = tf.reduce_sum(tf.square(diff), 2)
        diff *= self.mask

        cross_entropy = tf.reduce_sum(diff, 1)
        cross_entropy /= tf.cast(self.target_sequence_length, dtypes.float32)  # tf.reduce_sum(self.mask, 1)
        self.cost = tf.reduce_mean(cross_entropy)

        # Optimizer
        optimizer = tf.train.AdamOptimizer(self.learning_rate)

        # Gradient Clipping
        gradients = optimizer.compute_gradients(self.cost)
        capped_gradients = [(tf.clip_by_value(grad, -5., 5.), var) for grad, var in gradients if grad is not None]
        self.train_op = optimizer.apply_gradients(capped_gradients, global_step=self.global_step)

    def proprocess_samples(self, xs, ys=None):
        batch_size = len(xs)

        source_sequence_lens = np.array([len(x) for x in xs]).astype(np.int32)
        max_x_len = max(source_sequence_lens) + self.stop_pad_length
        padded_xs = []

        for x, lenx in zip(xs, source_sequence_lens):
            x_pad_length = max_x_len - lenx - self.stop_pad_length
            x_padding = np.full((x_pad_length, self.input_dim), self.pad_token, dtype=np.float32)
            padded_x = np.concatenate((x.astype(np.float32), self.x_stopping, x_padding))
            padded_xs.append(padded_x)

        padded_xs = np.array(padded_xs)

        if ys is not None:
            target_sequence_lens = np.array([len(y) for y in ys])
            max_y_len = max(target_sequence_lens) + self.stop_pad_length
            padded_ys = []
            mask = np.zeros((batch_size, max_y_len), dtype=np.float32)

            for y, leny, mask_ in zip(ys, target_sequence_lens, mask):
                y_pad_length = max_y_len - leny - self.stop_pad_length
                y_padding = np.full((y_pad_length, self.output_dim), self.pad_token, dtype=np.float32)
                padded_y = np.concatenate((y.astype(np.float32), self.y_stopping, y_padding))
                padded_ys.append(padded_y)
                mask_[:leny + self.stop_pad_length] = 1

            padded_ys = np.array(padded_ys)

            return padded_xs, padded_ys, source_sequence_lens, target_sequence_lens, mask

        target_sequence_lens = source_sequence_lens
        return padded_xs, source_sequence_lens, target_sequence_lens

    def debug(self, xs, ys):
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
            max_target_sequence_length = evaled[3]

            assert max_target_sequence_length == max(target_sequence_lens)

            diff = y_batch - predictions
            diff[np.isinf(diff)] = 0
            diff = np.sum(np.square(diff), 2)
            diff *= len_mask

            cross_entropy = np.sum(diff, 1)
            cross_entropy /= target_sequence_lens
            true_cost = np.mean(cross_entropy)

            assert np.allclose(true_cost, cost), 'Cost = {}, tru cost = {}'.format(cost, true_cost)
            print(('Lost = {}'.format(cost)))

    def train(self, training_gen, valid_gen, n_iterations=1500, batch_size=50, display_step=1):
        saver = tf.train.Saver(max_to_keep=1)
        with tf.Session() as sess:
            init = tf.global_variables_initializer()
            init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
            current_iteration = self.global_step.eval()
            for iteration in range(current_iteration, n_iterations):

                xs, ys = training_gen(batch_size)
                X_batch, y_batch, source_sequence_lens, target_sequence_lens, len_mask\
                    = self.proprocess_samples(xs, ys)

                actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
                actual_go_tokens = np.full((batch_size, 1, self.output_dim), self.go_token, dtype=np.float32)

                # Training step
                feed_dict = {
                    self.input_data: X_batch,
                    self.output_data: y_batch,
                    self.mask: len_mask,
                    self.start_tokens: actual_start_tokens,
                    self.go_tokens: actual_go_tokens,
                    self.target_sequence_length: target_sequence_lens,
                    self.source_sequence_length: source_sequence_lens
                }
                _, loss = sess.run([self.train_op, self.cost], feed_dict)

                # Debug message updating us on the status of the training
                if iteration % display_step == 0 or iteration == n_iterations - 1:
                    xs, ys = valid_gen(batch_size)
                    X_batch, y_batch, source_sequence_lens, target_sequence_lens, len_mask\
                        = self.proprocess_samples(xs, ys)

                    # Calculate validation cost
                    feed_dict = {
                        self.input_data: X_batch,
                        self.output_data: y_batch,
                        self.mask: len_mask,
                        self.start_tokens: actual_start_tokens,
                        self.go_tokens: actual_go_tokens,
                        self.target_sequence_length: target_sequence_lens,
                        self.source_sequence_length: source_sequence_lens
                    }
                    validation_loss = sess.run(self.cost, feed_dict)

                    print(('Epoch {:>3}/{} - Loss: {:>6.3f}  - Validation loss: {:>6.3f}'.
                           format(iteration, n_iterations, loss, validation_loss)))

                    saver.save(sess, self.saved_session_name, global_step=self.global_step)
                    self.copy_saved_to_zip()

    def recreate_session(self):
        saver = tf.train.Saver()
        init = tf.global_variables_initializer()
        session = tf.Session()
        session.run(init)
        saver.restore(session, tf.train.latest_checkpoint(self.tmp_folder))
        return session

    def _predict_or_encode(self, mode, test_seq, session=None):
        if mode == 'predict':
            ops = self.inference_decoder_output
        else:
            ops = self.enc_state

        batch_size = len(test_seq)
        X_batch, source_sequence_lens, target_sequence_lens = self.proprocess_samples(test_seq)

        actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
        feed_dict = {
            self.input_data: X_batch,
            self.start_tokens: actual_start_tokens,
            self.target_sequence_length: target_sequence_lens,
            self.source_sequence_length: source_sequence_lens
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

    def predict(self, test_seq, session=None, res_len=None):
        decoder_output = self._predict_or_encode('predict', test_seq, session)
        padded_output = decoder_output.rnn_output
        if res_len is None:
            return padded_output

        retval = []
        for y, leny in zip(padded_output, res_len):
            retval.append(y[:leny])
        return retval

    def encode(self, test_seq, session=None):
        states = self._predict_or_encode('encode', test_seq, session)
        return np.concatenate(states, axis=1)
