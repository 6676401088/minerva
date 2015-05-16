#!/usr/bin/env python
""" This module contains operations for convolution, pooling and softmax
"""
import athena as _owl

soft_op = _owl.softmax_algo
""" Same enum type as cudnn's ``cudnnSoftmaxMode_t``. Either ``soft_op.instance`` or ``soft_op.channel``.
"""
pool_op = _owl.pooling_algo
""" Same enum type as cudnn's ``cudnnPoolingMode_t``. Either ``pool_op.max`` or ``pool_op.avg``.
"""

def softmax(x, op = soft_op.instance):
    """ Perform softmax on the given ndarray.

    Note that this function is currently only for softmax accross instances. And the last
    dimension of ``x`` should represent instances. If ``x`` is of four dimension, directly
    call the c++ routine. Otherwise, augment the number of dimension to four.

    :param owl.NArray x: the ndarray to be softmaxed
    :param owl.conv.soft_op op: what type of softmax to perform
    :return: the ndarray after being softmaxed and of the same shape
    :rtype: owl.NArray
    """
    if len(x.shape) == 4:
        return _owl.NArray.softmax_forward(x, op)
    else:
        ori_shape = list(x.shape)
        soft_shape = x.shape[0:-1] + [1 for i in range(4 - len(ori_shape))] + [x.shape[-1]]
        return _owl.NArray.softmax_forward(x.reshape(soft_shape), op).reshape(ori_shape)

class Lrner:
    """ Wrapper class for LRN.

    :ivar int local_size: the size of lrn across channel
    :ivar float alpha: lrn parameters
    :ivar float beta: lrn parameters
    """
    def __init__(self, local_size, alpha, beta):
        """ Constructor for Convolver class

        :param int local_size: the size of lrn across channel
        :param float alpha: lrn parameters
        :param float beta: lrn parameters
        """
        self.local_size = local_size
        self.alpha = alpha
        self.beta = beta

    def ff(self, x, scale):
        """ Feed-forward local response norm

        :param owl.NArray x: input of the lrn
        :param owl.NArray scale: auxiliary matrix to help computing
        :return: result ndarray after forward lrn
        :rtype: owl.NArray
        """
        #print np.reshape(x.to_numpy(), np.prod(np.shape(x.to_numpy()))).tolist()[0:100]
        return _owl.NArray.lrn_forward(x, scale, self.local_size, self.alpha, self.beta)

    def bp(self, bottom_data, top_data, scale, top_diff):
        """ Backward local response norm

        :param owl.NArray bottom_data: activation before lrn
        :param owl.NArray top_data: activation after lrn
        :param owl.NArray scale: auxiliary matrix to help computing
        :param owl.NArray top_diff: error derivative
        :return: result ndarray after backward lrn
        :rtype: owl.NArray
        """
        return _owl.NArray.lrn_backward(bottom_data, top_data, scale, top_diff, self.local_size, self.alpha, self.beta)


class Convolver:
    """ Wrapper class for convolution.

    :ivar libowl.ConvInfo param: convolution parameters
    """
    def __init__(self, pad_h, pad_w, stride_v, stride_h):
        """ Constructor for Convolver class

        :param int pad_h: padding height
        :param int pad_w: padding width
        :param int stride_v: vertical stride length
        :param int stride_h: horizontal stride length
        """
        ci = _owl.ConvInfo()
        ci.pad_height = pad_h
        ci.pad_width = pad_w
        ci.stride_vertical = stride_v
        ci.stride_horizontal = stride_h
        self.param = ci

    def ff(self, x, w, b):
        """ Feed-forward convolution

        :param owl.NArray x: input of the convolution
        :param owl.NArray w: filters
        :param owl.NArray b: bias of the convolution
        :return: result ndarray after forward convolution
        :rtype: owl.NArray
        """
        return _owl.NArray.conv_forward(x, w, b, self.param)

    def bp(self, y, x, w):
        """ Backward convolution

        :param owl.NArray y: error of the convolution usually passed by higher layers
        :param owl.NArray x: bottom activation
        :param owl.NArray w: filters
        :return: result ndarray after backward convolution
        :rtype: owl.NArray
        """
        return _owl.NArray.conv_backward_data(y, x, w, self.param)

    def weight_grad(self, y, x, w):
        """ Compute the gradient of filters

        :param owl.NArray y: error (sensitivity) passed by higher layer
        :param owl.NArray x: input (activation) of lower layer
        :param owl.NArray w: weight (used to get the filter dimension)
        :return: the gradient of filters
        :rtype: owl.NArray
        """
        return _owl.NArray.conv_backward_filter(y, x, w, self.param)

    def bias_grad(self, y):
        """ Compute the gradient of bias

        :param owl.NArray y: error (sensitivity) passed by higher layer
        :return: the gradient of bias
        :rtype: owl.NArray
        """
        return _owl.NArray.conv_backward_bias(y)

class Pooler:
    """ Wrapper class for pooling operations

    :ivar libowl.PoolingInfo param: pooling parameters
    """
    def __init__(self, h, w, stride_v, stride_h, pad_h = 0, pad_w = 0, op = pool_op.max):
        """ Constructor for Pooler class

        :param int h: pooling height
        :param int w: pooling width
        :param int stride_v: vertical stride length
        :param int stride_h: horizontal stride length
        :param int pad_h: padding height
        :param int pad_w: padding width
        :param owl.conv.pool_op op: pooling type
        """
        pi = _owl.PoolingInfo()
        pi.height = h
        pi.width = w
        pi.stride_vertical = stride_v
        pi.stride_horizontal = stride_h
        pi.pad_height = pad_h
        pi.pad_width = pad_w
        pi.algorithm = op
        self.param = pi

    def ff(self, x):
        """ Forward propagation for pooling

        :param owl.NArray x: input ndarray of pooling
        :return: output ndarray after forward pooling
        :rtype: owl.NArray
        """

        #print "%d %d %d %d" % (self.param.height, self.param.width, self.param.stride_vertical, self.param.stride_horizontal)
        return _owl.NArray.pooling_forward(x, self.param)

    def bp(self, y, ff_y, ff_x):
        """ Backward propagation for pooling

        :param owl.NArray y: error (sensitivity) from higher-layer
        :param owl.NArray ff_y: value after forward pooling
        :param owl.NArray ff_x: value before forward pooling
        :return: output after backward pooling
        :rtype: owl.NArray
        """
        return _owl.NArray.pooling_backward(y, ff_y, ff_x, self.param)
