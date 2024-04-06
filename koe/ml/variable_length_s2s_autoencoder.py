import json
import os
import shutil
import zipfile
from uuid import uuid4

import tensorflow as tf

from root.utils import mkdirp


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


class VLS2SAutoEncoderFactory:
    def __init__(self):
        self.layer_sizes = []
        self.kernel_size = 0
        self.output_dim = 1
        self.input_dim = 1
        self.max_seq_len = 30
        self.learning_rate = 0.001
        self.tmp_folder = None
        self.uuid_code = None

    def build(self, save_to):
        if os.path.isfile(save_to):
            with zipfile.ZipFile(save_to, "r") as zip_file:
                namelist = zip_file.namelist()
                if "meta.json" in namelist:
                    meta = json.loads(zip_file.read("meta.json"))
                    for k, v in meta.items():
                        setattr(self, k, v)

        if self.uuid_code is None:
            self.uuid_code = uuid4().hex
        if self.tmp_folder is None:
            self.tmp_folder = os.path.join("/tmp", "VLS2SAutoEncoderFactory-{}".format(self.uuid_code))

        if os.path.exists(self.tmp_folder):
            shutil.rmtree(self.tmp_folder)
        mkdirp(self.tmp_folder)

        build_anew = True
        if os.path.isfile(save_to):
            has_saved_checkpoint = extract_saved(self.tmp_folder, save_to)
            build_anew = not has_saved_checkpoint

        params = vars(self)
        meta_file = os.path.join(self.tmp_folder, "meta.json")
        with open(meta_file, "w") as f:
            json.dump(params, f)

        retval = _VLS2SAutoEncoder(self)
        retval.save_to = save_to
        retval.build_anew = build_anew
        retval.construct()
        return retval


class _VLS2SAutoEncoder:
    def __init__(self, factory):
        self.global_step = tf.Variable(0, name="global_step", trainable=False)
        self.learning_rate = factory.learning_rate
        self.max_seq_len = factory.max_seq_len
        self.input_dim = factory.input_dim
        self.output_dim = factory.output_dim
        self.layer_sizes = factory.layer_sizes
        self.kernel_size = factory.kernel_size
        self.learning_rate = factory.learning_rate
        self.tmp_folder = factory.tmp_folder
        self.uuid_code = factory.uuid_code
        self.kernel_layer_idx = len(self.layer_sizes)

        self.outputs = None
        self.states = None
        self.loss = None
        self.optimizer = None
        self.training_op = None
        self.init = None
        self.X = None
        self.y = None
        self.sequence_length = None
        self.mask = None
        self.save_to = None
        self.saved_session_name = None
        self.build_anew = True

    def cleanup(self):
        shutil.rmtree(self.tmp_folder)

    def copy_saved_to_zip(self):
        save_to_bak = self.save_to + ".bak"
        save_to_bak2 = self.save_to + ".bak2"

        with zipfile.ZipFile(save_to_bak, "w", zipfile.ZIP_BZIP2, False) as zip_file:
            for root, dirs, files in os.walk(self.tmp_folder):
                for file in files:
                    with open(os.path.join(root, file), "rb") as f:
                        zip_file.writestr(file, f.read())

        if os.path.isfile(self.save_to):
            os.rename(self.save_to, save_to_bak2)
        os.rename(save_to_bak, self.save_to)
        if os.path.isfile(save_to_bak2):
            os.remove(save_to_bak2)

    def construct(self):
        self.saved_session_name = os.path.join(self.tmp_folder, self.uuid_code)
        self.X = tf.placeholder(tf.float32, [None, self.max_seq_len, self.input_dim])
        self.y = tf.placeholder(tf.float32, [None, self.max_seq_len, self.output_dim])
        self.sequence_length = tf.placeholder(tf.int32, [None])
        self.mask = tf.placeholder(tf.float32, [None, self.max_seq_len])

        encode_layer_cells = []
        for encode_layer_size in self.layer_sizes:
            encode_layer_cells.append(tf.contrib.rnn.GRUCell(num_units=encode_layer_size, activation=tf.nn.relu))
        kernel_cell = [tf.contrib.rnn.GRUCell(num_units=self.kernel_size, activation=tf.nn.relu)]

        decode_layer_cells = []
        for decode_layer_size in self.layer_sizes:
            decode_layer_cells.append(tf.contrib.rnn.GRUCell(num_units=decode_layer_size, activation=tf.nn.relu))

        cells = encode_layer_cells + kernel_cell + decode_layer_cells
        cells = tf.contrib.rnn.MultiRNNCell(cells)
        cell = tf.contrib.rnn.OutputProjectionWrapper(cells, output_size=self.output_dim)
        self.outputs, self.states = tf.nn.dynamic_rnn(
            cell, self.X, dtype=tf.float32, sequence_length=self.sequence_length
        )

        diff = tf.reduce_sum(tf.square(self.outputs - self.y), 2)
        diff *= self.mask

        cross_entropy = tf.reduce_sum(diff, 1)
        cross_entropy /= tf.reduce_sum(self.mask, 1)
        self.loss = tf.reduce_mean(cross_entropy)

        self.optimizer = tf.train.AdamOptimizer(learning_rate=self.learning_rate)
        self.training_op = self.optimizer.minimize(self.loss, global_step=self.global_step)
        self.init = tf.global_variables_initializer()

    def train(self, training_sample_generator, n_iterations=1500, batch_size=50):
        saver = tf.train.Saver(max_to_keep=1)
        with tf.Session() as sess:
            self.init.run()
            if not self.build_anew:
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
            current_iteration = self.global_step.eval()
            for iteration in range(current_iteration, n_iterations):
                X_batch, sequence_lens, len_mask = training_sample_generator(batch_size)
                y_batch = X_batch
                sess.run(
                    self.training_op,
                    feed_dict={
                        self.X: X_batch,
                        self.y: y_batch,
                        self.sequence_length: sequence_lens,
                        self.mask: len_mask,
                    },
                )
                if iteration % 10 == 0 or iteration == n_iterations - 1:
                    mse = self.loss.eval(
                        feed_dict={
                            self.X: X_batch,
                            self.y: y_batch,
                            self.sequence_length: sequence_lens,
                            self.mask: len_mask,
                        }
                    )
                    print("Iteration #{}/{} \t MSE: {}".format(iteration + 1, n_iterations, mse))
                    saver.save(sess, self.saved_session_name, global_step=self.global_step)
                    self.copy_saved_to_zip()

    def recreate_session(self):
        saver = tf.train.Saver()
        init = tf.global_variables_initializer()
        session = tf.Session()
        session.run(init)
        saver.restore(session, tf.train.latest_checkpoint(self.tmp_folder))
        return session

    def predict(self, test_seq, test_seq_len, session=None):
        if session is None:
            saver = tf.train.Saver()
            init = tf.global_variables_initializer()
            with tf.Session() as sess:
                init.run()
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
                y_pred = sess.run(
                    self.outputs,
                    feed_dict={self.X: test_seq, self.sequence_length: test_seq_len},
                )
                return y_pred
        else:
            y_pred = session.run(
                self.outputs,
                feed_dict={self.X: test_seq, self.sequence_length: test_seq_len},
            )
            return y_pred

    def encode(self, test_seq, test_seq_len, session=None):
        if session is None:
            saver = tf.train.Saver()
            init = tf.global_variables_initializer()
            with tf.Session() as sess:
                init.run()
                saver.restore(sess, tf.train.latest_checkpoint(self.tmp_folder))
                states = sess.run(
                    self.states,
                    feed_dict={self.X: test_seq, self.sequence_length: test_seq_len},
                )
        else:
            states = session.run(
                self.states,
                feed_dict={self.X: test_seq, self.sequence_length: test_seq_len},
            )
        return states[self.kernel_layer_idx]
