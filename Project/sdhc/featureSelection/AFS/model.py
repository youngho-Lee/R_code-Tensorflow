# https://github.com/upup123/AAAI-2019-AFS

import tensorflow.compat.v1 as tf
tf.disable_v2_behavior()

import numpy as np
from utils import BatchCreate

# parameter
input_size = 889
output_size = 1
E_node = 128 # 32
A_node = 32
AO_node = 2
set_seed = 42
L_node = 500
moving_average_decay = 0.99

regularization_rate = 0.0001
learning_rate_base = 0.01
learning_rate_decay = 0.99
batch_size = 1024
train_step = 2000


# implementation
def build(total_batch):
    X = tf.placeholder(tf.float32, [None, input_size])
    Y = tf.placeholder(tf.float32, [None, output_size])
    global_step = tf.Variable(0, trainable=False)

    tf.add_to_collection('input', X)
    tf.add_to_collection('output', Y)

    with tf.variable_scope('attention_module') as scope:
        E_W = tf.Variable(tf.truncated_normal([input_size, E_node], stddev=0.1, seed=set_seed))
        E_b = tf.Variable(tf.constant(0.1, shape=[E_node]))

        E = tf.nn.tanh(tf.matmul(X, E_W) + E_b)

        A_W1 = tf.Variable(tf.truncated_normal([input_size, E_node, A_node], stddev=0.1, seed=set_seed))
        A_b1 = tf.Variable(tf.constant(0.1, shape=[input_size, A_node]))
        A_W2 = tf.Variable(tf.truncated_normal([input_size, A_node, AO_node], stddev=0.1, seed=set_seed))
        A_b2 = tf.Variable(tf.constant(0.1, shape=[input_size, AO_node]))

        A_W1_unstack = tf.unstack(A_W1, axis=0)
        A_b1_unstack = tf.unstack(A_b1, axis=0)
        A_W2_unstack = tf.unstack(A_W2, axis=0)
        A_b2_unstack = tf.unstack(A_b2, axis=0)

        attention_out_list = []
        for i in range(input_size):
            attention_FC1 = tf.matmul(E, A_W1_unstack[i]) + A_b1_unstack[i]
            attention_FC2 = tf.matmul(attention_FC1, A_W2_unstack[i]) + A_b2_unstack[i]
            attention_out = tf.nn.softmax(attention_FC2)

            attention_out = tf.expand_dims(attention_out[:,1], axis=1)

            attention_out_list.append(attention_out)
        A = tf.squeeze(tf.stack(attention_out_list, axis=1), axis=2)

    with tf.variable_scope("learning_module") as scope:
        G = tf.multiply(X, A)
        L_W1 = tf.Variable(tf.truncated_normal([input_size, L_node], stddev=0.1, seed=set_seed))
        L_b1 = tf.Variable(tf.constant(0.1, shape=[L_node]))
        L_W2 = tf.Variable(tf.truncated_normal([L_node, output_size], stddev=0.1, seed=set_seed))
        L_b2 = tf.Variable(tf.constant(0.1, shape=[output_size]))

        variable_averages = tf.train.ExponentialMovingAverage(moving_average_decay, global_step)
        variable_averages_op = variable_averages.apply(tf.trainable_variables())
        L_FC = tf.nn.relu(tf.matmul(G, L_W1) + L_b1)
        O = tf.nn.sigmoid(tf.matmul(L_FC, L_W2) + L_b2)

        average_L_FC = tf.nn.relu(tf.matmul(G, variable_averages.average(L_W1)) + variable_averages.average(L_b1))
        average_O = tf.nn.sigmoid(tf.matmul(average_L_FC, variable_averages.average(L_W2)) + variable_averages.average(L_b2))

    with tf.name_scope("Loss") as scope:
        regularizer = tf.keras.regularizers.L2(regularization_rate)
        regularization = regularizer(L_W1) + regularizer(L_W2)

        learning_rate = tf.train.exponential_decay(learning_rate_base, global_step, total_batch, learning_rate_decay)

        cross_entropy = tf.nn.sigmoid_cross_entropy_with_logits(logits=O, labels=Y)
        cross_entropy_mean = tf.reduce_mean(cross_entropy)
        loss = cross_entropy_mean + regularization

        correct_prediction = tf.equal(tf.round(average_O), tf.round(Y))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    with tf.name_scope("Train") as scope:
        vars_A = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='attention_module')
        vars_L = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='learning_module')
        vars_R = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='Loss')
        
        # Minimizing Loss Function
        optimizer = tf.train.GradientDescentOptimizer(learning_rate).minimize(
            loss, global_step=global_step, var_list=[vars_A, vars_L, vars_R])

    with tf.control_dependencies([optimizer, variable_averages_op]):
        train_op = tf.no_op(name='train')
    for op in [train_op, A]:
        tf.add_to_collection('train_ops', op)
    for op in [loss, accuracy]:
        tf.add_to_collection('validate_ops', op)


def test(input_size, train_X, train_Y, test_X, test_Y, total_batch, index):
    X = tf.placeholder(tf.float32, [None, input_size])
    Y = tf.placeholder(tf.float32, [None, output_size])
    global_step = tf.Variable(0, trainable=False)

    with tf.variable_scope("test_model_{}".format(index)) as scope:
        L_W1 = tf.Variable(tf.truncated_normal([input_size, L_node], stddev=0.1, seed=set_seed))
        L_b1 = tf.Variable(tf.constant(0.1, shape=[L_node]))
        L_W2 = tf.Variable(tf.truncated_normal([L_node, output_size], stddev=0.1, seed=set_seed))
        L_b2 = tf.Variable(tf.constant(0.1, shape=[output_size]))

        variable_averages = tf.train.ExponentialMovingAverage(moving_average_decay, global_step)
        variable_averages_op = variable_averages.apply(
            tf.trainable_variables(scope='test_model_{}'.format(index)))
        L_FC = tf.nn.relu(tf.matmul(X, L_W1) + L_b1)
        O = tf.nn.sigmoid(tf.matmul(L_FC, L_W2) + L_b2)

        average_L_FC = tf.nn.relu(tf.matmul(X, variable_averages.average(L_W1)) + variable_averages.average(L_b1))
        average_O = tf.nn.sigmoid(tf.matmul(average_L_FC, variable_averages.average(L_W2)) + variable_averages.average(L_b2))

    with tf.name_scope("test_Loss_{}".format(index)) as scope:
        regularizer = tf.keras.regularizers.L2(regularization_rate)
        regularization = regularizer(L_W1) + regularizer(L_W2)

        learning_rate = tf.train.exponential_decay(learning_rate_base, global_step, total_batch, learning_rate_decay)

        cross_entropy = tf.nn.sigmoid_cross_entropy_with_logits(logits=O, labels=Y)
        cross_entropy_mean = tf.reduce_mean(cross_entropy)
        loss = cross_entropy_mean + regularization

        correct_prediction = tf.equal(tf.round(average_O), tf.round(Y))
        accuracy = tf.reduce_mean(tf.cast(correct_prediction, tf.float32))

    with tf.name_scope("Train") as scope:
        vars_m = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='test_model_{}'.format(index))
        vars_l = tf.get_collection(tf.GraphKeys.TRAINABLE_VARIABLES, scope='test_Loss_{}'.format(index))
        
        # Minimizing Loss Function
        optimizer = tf.train.GradientDescentOptimizer(learning_rate).minimize(
            loss, global_step=global_step, var_list=[vars_m, vars_l])

    with tf.control_dependencies([optimizer, variable_averages_op]):
        train_op = tf.no_op(name='train_{}'.format(index))

    Iterator = BatchCreate(train_X, train_Y)

    with tf.Session() as sess:
        tf.global_variables_initializer().run()

        for step in range(1, train_step + 1):
            xs, ys = Iterator.next_batch(batch_size)
            sess.run(train_op, feed_dict={X: xs, Y: np.expand_dims(ys, axis=1)})
        accuracy = sess.run(accuracy, feed_dict={X: test_X, Y: np.expand_dims(test_Y, axis=1)})

    return accuracy
