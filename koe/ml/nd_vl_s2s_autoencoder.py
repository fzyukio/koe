import json
import os
import shutil
import time
import zipfile
from signal import SIGABRT, SIGINT, SIGTERM, SIGUSR1, signal
from uuid import uuid4

import numpy as np
import tensorflow as tf
from tensorboard.compat.tensorflow_stub import dtypes
from tensorflow.contrib.seq2seq import BasicDecoder, InferenceHelper, TrainingHelper, dynamic_decode
from tensorflow.nn import dynamic_rnn, relu

from koe.ml.learning_rate_funcs import lrfunc_classes
from root.utils import mkdirp


tf.logging.set_verbosity(tf.logging.ERROR)
regularizer = tf.contrib.layers.l2_regularizer(scale=0.1)


def make_cell(layer_sizes, keep_prob=None):
    cells = []
    for layer_size in layer_sizes:
        cell = tf.contrib.rnn.GRUCell(
            layer_size,
            # bias_initializer=tf.initializers.he_normal(),
            # kernel_initializer=tf.initializers.he_normal(),
            bias_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
            kernel_initializer=tf.random_uniform_initializer(-0.1, 0.1, seed=2),
            # kernel_regularizer=regularizer,
            activation=relu,
        )
        cells.append(cell)

    lstm = tf.contrib.rnn.MultiRNNCell(cells)
    if keep_prob:
        return tf.contrib.rnn.DropoutWrapper(lstm, input_keep_prob=keep_prob)
    else:
        return lstm


def extract_saved(tmp_folder, filepath):
    has_saved_checkpoint = False
    with zipfile.ZipFile(filepath, "r") as zip_file:
        namelist = zip_file.namelist()
        for name in namelist:
            if name == "checkpoint":
                has_saved_checkpoint = True
            filecontent = zip_file.read(name)
            filepath = os.path.join(tmp_folder, name)
            with open(filepath, "wb") as f:
                f.write(filecontent)
    return has_saved_checkpoint


class NDS2SAEFactory:
    def __init__(self):
        self.layer_sizes = []
        self.output_dim = 1
        self.input_dim = 1
        self.tmp_folder = None
        self.uuid_code = None
        self.stop_pad_length = 5
        self.stop_pad_token = 0
        self.pad_token = 100
        self.go_token = -100.0
        self.keep_prob = None
        self.symmetric = True
        self.lrtype = "constant"
        self.lrargs = dict(lr=0.001)
        self.write_summary = False
        self._save_to = None

    def set_output(self, filename):
        self._save_to = filename
        if os.path.isfile(filename):
            with zipfile.ZipFile(filename, "r") as zip_file:
                namelist = zip_file.namelist()
                if "meta.json" in namelist:
                    meta = json.loads(str(zip_file.read("meta.json"), "utf-8"))
                    for k, v in list(meta.items()):
                        if not callable(v) and not k.startswith("_"):
                            setattr(self, k, v)

    def build(self):
        if self._save_to is None:
            raise Exception("Must call set_output(_save_to=...) first")

        assert self.lrtype in list(lrfunc_classes.keys())

        if self.uuid_code is None:
            self.uuid_code = uuid4().hex
        if self.tmp_folder is None:
            self.tmp_folder = os.path.join("/tmp", "NDS2SAE-{}".format(self.uuid_code))

        if os.path.exists(self.tmp_folder):
            shutil.rmtree(self.tmp_folder)
        mkdirp(self.tmp_folder)

        build_anew = True
        if os.path.isfile(self._save_to):
            has_saved_checkpoint = extract_saved(self.tmp_folder, self._save_to)
            build_anew = not has_saved_checkpoint

        params = {v: k for v, k in list(vars(self).items()) if not callable(k)}
        meta_file = os.path.join(self.tmp_folder, "meta.json")
        with open(meta_file, "w") as f:
            json.dump(params, f)

        lrfunc_class = lrfunc_classes[self.lrtype]

        retval = _NDS2SAE(self)
        retval.learning_rate_func = lrfunc_class(**self.lrargs).get_lr
        retval._save_to = self._save_to
        retval.build_anew = build_anew
        retval.construct()
        return retval


class _NDS2SAE:
    def __init__(self, factory):
        self.global_step = tf.Variable(0, name="global_step", trainable=False)
        self.input_dim = factory.input_dim
        self.output_dim = factory.output_dim
        self.layer_sizes = factory.layer_sizes

        self.tmp_folder = factory.tmp_folder
        self.uuid_code = factory.uuid_code
        self.latent_dims = sum(self.layer_sizes)
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
        self.enc_state_centre = None
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
            print(("Cleaned up temp folder {}".format(self.tmp_folder)))
            shutil.rmtree(self.tmp_folder)

    def copy_saved_to_zip(self):
        save_to_bak = self._save_to + ".bak"
        save_to_bak2 = self._save_to + ".bak2"

        with zipfile.ZipFile(save_to_bak, "w", zipfile.ZIP_BZIP2, False) as zip_file:
            for root, dirs, files in os.walk(self.tmp_folder):
                for file in files:
                    with open(os.path.join(root, file), "rb") as f:
                        zip_file.writestr(file, f.read())

        if os.path.isfile(self._save_to):
            os.rename(self._save_to, save_to_bak2)
        os.rename(save_to_bak, self._save_to)
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
        self.target_sequence_length = tf.placeholder(tf.int32, (None,), name="target_sequence_length")
        self.max_target_sequence_length = tf.reduce_max(self.target_sequence_length, name="max_target_len")
        self.source_sequence_length = tf.placeholder(tf.int32, (None,), name="source_sequence_length")
        self.x_stopping = np.full(
            (self.stop_pad_length, self.input_dim),
            self.stop_pad_token,
            dtype=np.float32,
        )
        self.y_stopping = np.full(
            (self.stop_pad_length, self.output_dim),
            self.stop_pad_token,
            dtype=np.float32,
        )
        self.learning_rate = tf.placeholder(tf.float32)
        self.batch_size = tf.placeholder(tf.float32)

        enc_cell = make_cell(self.layer_sizes, self.keep_prob)

        # We want to train the decoder to learn the stopping point as well,
        # so the sequence lengths is extended for both the decoder and the encoder
        # logic: the encoder will learn that the stopping token is the signal that the input is finished
        #        the decoder will learn to produce the stopping token to match the expected output
        #        the inferer will learn to produce the stopping token for us to recognise that and stop inferring
        self.source_sequence_length_padded = self.source_sequence_length + self.stop_pad_length
        self.target_sequence_length_padded = self.target_sequence_length + self.stop_pad_length
        max_target_sequence_length_padded = self.max_target_sequence_length + self.stop_pad_length

        _, self.enc_state = dynamic_rnn(
            enc_cell,
            self.input_data,
            sequence_length=self.source_sequence_length_padded,
            dtype=tf.float32,
            time_major=False,
            swap_memory=True,
        )
        self.enc_state_centre = self.enc_state[-1]

        if self.symmetric:
            self.enc_state = self.enc_state[::-1]
            dec_cell = make_cell(self.layer_sizes[::-1], self.keep_prob)
        else:
            dec_cell = make_cell(self.layer_sizes, self.keep_prob)

        # 3. Dense layer to translate the decoder's output at each time
        # step into a choice from the target vocabulary
        projection_layer = tf.layers.Dense(
            units=self.output_dim,
            # kernel_initializer=tf.initializers.he_normal(),
            # kernel_regularizer=regularizer,
            kernel_initializer=tf.truncated_normal_initializer(mean=0.0, stddev=0.1),
        )

        # 4. Set up a training decoder and an inference decoder
        # Training Decoder
        with tf.variable_scope("decode"):
            # During PREDICT mode, the output data is none so we can't have a training model.
            # Helper for the training process. Used by BasicDecoder to read inputs.
            dec_input = tf.concat([self.go_tokens, self.output_data], 1)
            training_helper = TrainingHelper(
                inputs=dec_input,
                sequence_length=self.target_sequence_length_padded,
                time_major=False,
            )

            # Basic decoder
            training_decoder = BasicDecoder(dec_cell, training_helper, self.enc_state, projection_layer)

            # Perform dynamic decoding using the decoder
            self.training_decoder_output = dynamic_decode(
                training_decoder,
                # True because we're using variable length sequences, which have finish points
                impute_finished=True,
                maximum_iterations=max_target_sequence_length_padded,
            )[0]
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
                end_fn=end_fn,
            )

            # Basic decoder
            inference_decoder = BasicDecoder(dec_cell, inference_helper, self.enc_state, projection_layer)

            # Perform dynamic decoding using the decoder
            self.inference_decoder_output = dynamic_decode(
                inference_decoder,
                # True because we're using variable length sequences, which have finish points
                impute_finished=True,
                maximum_iterations=max_target_sequence_length_padded,
            )[0]

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
                mask_[: leny + self.stop_pad_length] = 1

            padded_ys = np.array(padded_ys)

            return (
                padded_xs,
                padded_ys,
                source_sequence_lens,
                target_sequence_lens,
                mask,
            )

        target_sequence_lens = source_sequence_lens
        return padded_xs, source_sequence_lens, target_sequence_lens

    def debug(self, xs, ys):
        self.construct_loss_function()
        saver = tf.train.Saver(max_to_keep=1)
        batch_size = len(xs)
        with tf.Session() as sess:
            init = tf.global_variables_initializer()
            init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))

            (
                X_batch,
                y_batch,
                source_sequence_lens,
                target_sequence_lens,
                len_mask,
            ) = self.proprocess_samples(xs, ys)

            actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
            actual_go_tokens = np.full((batch_size, 1, self.output_dim), self.go_token, dtype=np.float32)

            # Training step
            evaled = sess.run(
                [self.train_op, self.cost, self.predictions],
                {
                    self.batch_size: batch_size,
                    self.learning_rate: 0,
                    self.input_data: X_batch,
                    self.output_data: y_batch,
                    self.mask: len_mask,
                    self.start_tokens: actual_start_tokens,
                    self.go_tokens: actual_go_tokens,
                    self.target_sequence_length: target_sequence_lens,
                    self.source_sequence_length: source_sequence_lens,
                },
            )
            cost = evaled[1]
            predictions = evaled[2]

            diff = y_batch - predictions
            diff[np.isinf(diff)] = 0
            diff = np.sum(np.square(diff), 2)
            diff *= len_mask

            cross_entropy = np.sum(diff, 1)
            cross_entropy /= target_sequence_lens + self.stop_pad_length
            true_cost = np.mean(cross_entropy)

            assert np.allclose(true_cost, cost), "Cost = {}, tru cost = {}".format(cost, true_cost)
            print(("Lost = {}".format(cost)))

    def construct_loss_function(self):
        if self.train_op is None:
            self.predictions = self.training_decoder_output.rnn_output

            target_sequence_length_padded_float32 = tf.cast(self.target_sequence_length_padded, dtypes.float32)

            # first take square difference. diff_sq.shaeoe = [batch_size, length, output_dim]
            diff = self.output_data - self.predictions
            diff_sq = tf.square(diff)

            # To avoid nan, instead of sum and divide, we divide and then sum
            # After this, we get squared difference normalised by the actual lengths of the sequences
            diff_sq_div_len = tf.math.divide(diff_sq, tf.reshape(target_sequence_length_padded_float32, (-1, 1, 1)))

            # Now, remove the elements that are padded
            diff_sq_div_len_masked = diff_sq_div_len * tf.expand_dims(self.mask, -1)

            # The cost is sum along dimension 2 (output dimension), then dimension 1 (time-axis), then
            # take the mean of the batch
            sum_diff_sq_div_len_masked = tf.reduce_sum(tf.reduce_sum(diff_sq_div_len_masked, axis=2), axis=1)
            self.cost = tf.reduce_sum(sum_diff_sq_div_len_masked / self.batch_size)

            # Optimizer
            optimizer = tf.train.AdamOptimizer(self.learning_rate)

            # Gradient Clipping
            gradients = optimizer.compute_gradients(self.cost)
            capped_gradients = [
                (tf.clip_by_value(grad, -5.0, 5.0), var) for grad, var in gradients if grad is not None
            ]
            self.train_op = optimizer.apply_gradients(capped_gradients)
            self.train_op_eob = optimizer.apply_gradients(capped_gradients, global_step=self.global_step)

    def train(
        self,
        training_gen,
        valid_gen,
        n_iterations=1500,
        batch_size=50,
        display_step=1,
        save_step=100,
    ):
        self.construct_loss_function()

        with tf.name_scope("summaries"):
            tf.summary.scalar("learning_rate", self.learning_rate)
            tf.summary.scalar("cost", self.cost)

        saver = tf.train.Saver(max_to_keep=1)
        with tf.Session() as sess:
            # Merge all the summaries and write them out to /tmp/mnist_logs (by default)
            if self.write_summary:
                summary_merged = tf.summary.merge_all()
                train_writer = tf.summary.FileWriter(self.tmp_folder + "/train", graph=sess.graph)
                test_writer = tf.summary.FileWriter(self.tmp_folder + "/test")
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
                    xs, ys, final_batch = training_gen(batch_size)
                    actual_batch_size = len(xs)
                    (
                        X_batch,
                        y_batch,
                        source_sequence_lens,
                        target_sequence_lens,
                        len_mask,
                    ) = self.proprocess_samples(xs, ys)

                    actual_start_tokens = np.full(
                        (actual_batch_size, self.output_dim),
                        self.go_token,
                        dtype=np.float32,
                    )
                    actual_go_tokens = np.full(
                        (actual_batch_size, 1, self.output_dim),
                        self.go_token,
                        dtype=np.float32,
                    )

                    # Training step
                    feed_dict = {
                        self.batch_size: actual_batch_size,
                        self.learning_rate: current_lr,
                        self.input_data: X_batch,
                        self.output_data: y_batch,
                        self.mask: len_mask,
                        self.start_tokens: actual_start_tokens,
                        self.go_tokens: actual_go_tokens,
                        self.target_sequence_length: target_sequence_lens,
                        self.source_sequence_length: source_sequence_lens,
                    }

                    if final_batch:
                        train_op = self.train_op_eob
                    else:
                        train_op = self.train_op

                    if self.write_summary:
                        _, loss, current_lr, summary = sess.run(
                            [train_op, self.cost, self.learning_rate, summary_merged],
                            feed_dict,
                        )
                        train_writer.add_summary(summary, iteration)
                    else:
                        _, loss, current_lr = sess.run([train_op, self.cost, self.learning_rate], feed_dict)

                # Debug message updating us on the status of the training
                if iteration % display_step == 0 or iteration == n_iterations - 1:
                    xs, ys, _ = valid_gen(batch_size=None)
                    actual_batch_size = len(xs)
                    (
                        X_batch,
                        y_batch,
                        source_sequence_lens,
                        target_sequence_lens,
                        len_mask,
                    ) = self.proprocess_samples(xs, ys)
                    actual_start_tokens = np.full(
                        (actual_batch_size, self.output_dim),
                        self.go_token,
                        dtype=np.float32,
                    )
                    actual_go_tokens = np.full(
                        (actual_batch_size, 1, self.output_dim),
                        self.go_token,
                        dtype=np.float32,
                    )

                    # Calculate validation cost
                    feed_dict = {
                        self.batch_size: actual_batch_size,
                        self.learning_rate: current_lr,
                        self.input_data: X_batch,
                        self.output_data: y_batch,
                        self.mask: len_mask,
                        self.start_tokens: actual_start_tokens,
                        self.go_tokens: actual_go_tokens,
                        self.target_sequence_length: target_sequence_lens,
                        self.source_sequence_length: source_sequence_lens,
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

                    print(
                        (
                            "Ep {:>4}/{} | Losses: {:>7.5f}/{:>7.5f} | LR: {:>6.5f} | Speed: {:>6.1f} ms/Ep".format(
                                iteration,
                                n_iterations,
                                loss,
                                validation_loss,
                                current_lr,
                                mean_duration,
                            )
                        )
                    )

                if iteration % save_step == 0 or iteration == n_iterations - 1:
                    start_time_save = int(round(time.time() * 1000))
                    saver.save(sess, self.saved_session_name, global_step=self.global_step)
                    self.copy_saved_to_zip()
                    duration_save = int(round(time.time() * 1000)) - start_time_save
                    print("Saved. Elapsed: {:>6.3f} ms".format(duration_save))

    def recreate_session(self):
        saver = tf.train.Saver()
        init = tf.global_variables_initializer()
        session = tf.Session()
        session.run(init)
        saver.restore(session, tf.train.latest_checkpoint(self.tmp_folder))
        return session

    def _predict_or_encode(self, mode, test_seq, session=None):
        if mode == "predict":
            ops = self.inference_decoder_output
        elif mode == "encode":
            ops = self.enc_state
        else:
            ops = self.enc_state_centre

        batch_size = len(test_seq)
        X_batch, source_sequence_lens, target_sequence_lens = self.proprocess_samples(test_seq)

        actual_start_tokens = np.full((batch_size, self.output_dim), self.go_token, dtype=np.float32)
        feed_dict = {
            self.input_data: X_batch,
            self.start_tokens: actual_start_tokens,
            self.target_sequence_length: target_sequence_lens,
            self.source_sequence_length: source_sequence_lens,
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
        decoder_output = self._predict_or_encode("predict", test_seq, session)
        padded_output = decoder_output.rnn_output
        if res_len is None:
            return padded_output

        retval = []
        for y, leny in zip(padded_output, res_len):
            retval.append(y[:leny])
        return retval

    def encode(self, test_seq, session=None, kernel_only=False):
        if kernel_only:
            states = self._predict_or_encode("encode-centre", test_seq, session)
            return states
        else:
            states = self._predict_or_encode("encode", test_seq, session)
            return np.concatenate(states, axis=1)
