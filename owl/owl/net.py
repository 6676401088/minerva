import owl
import owl.elewise as ele
import owl.conv as co
import numpy as np
import math
import Queue
from caffe import *
from netio import ImageNetDataProvider

class ComputeUnit(object):
    def __init__(self, params):
        self.params = params
        self.name = params.name
        self.btm_names = []
        self.top_names = []
    def __str__(self):
        return 'N/A unit'
    def forward(self, from_btm, to_top, phase):
        pass
    def backward(self, from_top, to_btm, phase):
        pass
    def weight_update(self, base_lr, base_weight_decay, momentum, batch_size):
        pass

class ComputeUnitSimple(ComputeUnit):
    def __init__(self, params):
        super(ComputeUnitSimple, self).__init__(params)
    def forward(self, from_btm, to_top, phase):
        to_top[self.top_names[0]] = self.ff(from_btm[self.btm_names[0]], phase)
    def ff(self, act, phase):
        pass
    def backward(self, from_top, to_btm, phase):
        to_btm[self.btm_names[0]] = self.bp(from_top[self.top_names[0]])
    def bp(self, sen):
        pass

class WeightedComputeUnit(ComputeUnitSimple):
    def __init__(self, params):
        super(WeightedComputeUnit, self).__init__(params)
        self.params = params
        # weights and bias
        self.weight = None
        self.weightdelta = None
        self.weightgrad = None
        self.bias = None
        self.biasdelta = None
        self.biasgrad = None
        # blob learning rate and weight decay
        self.blobs_lr = params.blobs_lr
        self.weight_decay = params.weight_decay
        if len(self.blobs_lr) == 0:
            self.blobs_lr = [1,1]
        if len(self.weight_decay) == 0:
            self.weight_decay = [1, 0]

    def weight_update(self, base_lr, base_weight_decay, momentum, batch_size):
        #TODO: need recheck with caffe with what's the multiplier for weight decay
        if self.weightdelta == None:
            self.weightdelta = owl.zeros(self.weightgrad.shape)

        self.weightdelta = momentum * self.weightdelta - (base_lr * self.blobs_lr[0] / batch_size) * self.weightgrad  - (base_lr * self.blobs_lr[0] * base_weight_decay * self.weight_decay[0]) * self.weight
        self.weight = self.weight + self.weightdelta
        self.weightgrad = None

        if self.biasdelta == None:
            self.biasdelta = owl.zeros(self.biasgrad.shape)

        self.biasdelta = momentum * self.biasdelta - (base_lr * self.blobs_lr[1] / batch_size) * self.biasgrad - (base_lr * self.blobs_lr[1] * base_weight_decay * self.weight_decay[1]) * self.bias
        self.bias = self.bias + self.biasdelta
        self.biasgrad = None

class LinearUnit(ComputeUnitSimple):
    def ff(self, x, phase):
        return x
    def bp(self, y):
        return y
    def __str__(self):
        return 'linear'

class SigmoidUnit(ComputeUnitSimple):
    def ff(self, x, phase):
        return ele.sigm(x)
    def bp(self, y):
        return ele.sigm_back(y)
    def __str__(self):
        return 'sigmoid'

class ReluUnit(ComputeUnitSimple):
    def ff(self, x, phase):
        self.ff_x = x
        return ele.relu(x)
    def bp(self, y):
        return ele.relu_back(y, self.ff_x)
    def __str__(self):
        return 'relu'

class TanhUnit(ComputeUnitSimple):
    def ff(self, x, phase):
        return ele.tanh(x)
    def bp(self, y):
        return ele.tanh_back(y)
    def __str__(self):
        return 'tanh'

class PoolingUnit(ComputeUnitSimple):
    def __init__(self, params):
        super(PoolingUnit, self).__init__(params)
        ppa = params.pooling_param
        if ppa.pool == PoolingParameter.PoolMethod.Value('MAX'):
            pool_ty = co.pool_op.max
        elif ppa.pool == PoolingParameter.PoolMethod.Value('AVE'):
            pool_ty = co.pool_op.avg
        self.pooler = co.Pooler(ppa.kernel_size, ppa.kernel_size, ppa.stride, ppa.stride, ppa.pad, ppa.pad, pool_ty)
    def ff(self, x, phase):
        self.ff_x = x
        self.ff_y = self.pooler.ff(x)
        return self.ff_y
    def bp(self, y):
        return self.pooler.bp(y, self.ff_y, self.ff_x)
    def __str__(self):
        return 'pooling'

class DropoutUnit(ComputeUnitSimple):
    def __init__(self, params):
        super(DropoutUnit, self).__init__(params)
        self.scale = 1.0 / (1.0 - self.params.dropout_param.dropout_ratio)
        self.keep_ratio = 1 - self.params.dropout_param.dropout_ratio
    def ff(self, x, phase):
        self.dropmask = owl.randb(x.shape, self.keep_ratio)
        if phase == "TRAIN":
            return ele.mult(x, self.dropmask)*self.scale
        else:
            #return x * (1 - self.params.dropout_param.dropout_ratio)
            return x

        '''
        #for gradient test
        return x
        '''
    def bp(self, y):
        return ele.mult(y, self.dropmask)*self.scale
        '''
        #for gradient test
        return y
        '''
    def __str__(self):
        return 'dropout'

class SoftmaxUnit(ComputeUnit):
    def __init__(self, params):
        super(SoftmaxUnit, self).__init__(params)
        self.loss_weight = params.loss_weight
    def forward(self, from_btm, to_top, phase):
        to_top[self.top_names[0]] = co.softmax(from_btm[self.btm_names[0]], co.soft_op.instance)
        self.ff_y = to_top[self.top_names[0]]
        self.y = from_btm[self.btm_names[1]]
    def backward(self, from_top, to_btm, phase):
        if len(self.loss_weight) == 1:
            to_btm[self.btm_names[0]] = (self.ff_y - self.y)*self.loss_weight[0]
        else:
            to_btm[self.btm_names[0]] = (self.ff_y - self.y)


    def getloss(self):
        #get accuracy
        '''
        batch_size = self.ff_y.shape[1]
        predict = self.ff_y.argmax(0)
        ground_truth = self.y.argmax(0)
        correct = (predict - ground_truth).count_zero()
        acc = 1 - (batch_size - correct) * 1.0 / batch_size
        print acc
        '''

        lossmat = ele.mult(ele.ln(self.ff_y), self.y)
        res = lossmat.sum(0).sum(1).to_numpy()
        return -res[0][0] / lossmat.shape[1]

        '''
        outputlist = self.ff_y.to_numpy()
        outputshape = np.shape(outputlist)
        outputlist = outputlist.reshape(np.prod(outputshape[0:len(outputshape)]))
        labellist = self.y.to_numpy().reshape(np.prod(outputshape[0:len(outputshape)]))
        res = 0
        for i in xrange(np.prod(outputshape[0:len(outputshape)])):
            if labellist[i] > 0.5:
                res -= math.log(outputlist[i])
        #print res
        return res
        '''

    def __str__(self):
        return 'softmax'

class AccuracyUnit(ComputeUnit):
    def __init__(self, params):
        super(AccuracyUnit, self).__init__(params)
        self.acc = 0
        self.batch_size = 0
    def forward(self, from_btm, to_top, phase):
        predict = from_btm[self.btm_names[0]].argmax(0)
        ground_truth = from_btm[self.btm_names[1]].argmax(0)
        self.batch_size = from_btm[self.btm_names[0]].shape[1]
        correct = (predict - ground_truth).count_zero()
        self.acc = 1 - (self.batch_size - correct) * 1.0 / self.batch_size

    def backward(self, from_top, to_btm, phase):
        pass
    def __str__(self):
        return 'accuracy'

class LRNUnit(ComputeUnitSimple):
    def __init__(self, params):
        super(LRNUnit, self).__init__(params)
        self.lrner = co.Lrner(params.lrn_param.local_size, params.lrn_param.alpha, params.lrn_param.beta)
        self.scale = None
    def ff(self, x, phase):
        self.ff_x = x
        self.scale = owl.zeros(x.shape)
        self.ff_y = self.lrner.ff(x, self.scale)
        return self.ff_y
    def bp(self, y):
        return self.lrner.bp(self.ff_x, self.ff_y, self.scale, y)
    def __str__(self):
        return 'lrn'

class ConcatUnit(ComputeUnit):
    def __init__(self, params):
        super(ConcatUnit, self).__init__(params)
        self.concat_dim_caffe = params.concat_param.concat_dim
        self.slice_count = []
    def forward(self, from_btm, to_top, phase):
        narrays = []
        self.concat_dim = len(from_btm[self.btm_names[0]].shape) - 1 - self.concat_dim_caffe
        for i in range(len(self.btm_names)):
            narrays.append(from_btm[self.btm_names[i]])
            self.slice_count.append(from_btm[self.btm_names[i]].shape[self.concat_dim])
        to_top[self.top_names[0]] = owl.concat(narrays, self.concat_dim)
    def backward(self, from_top, to_btm, phase):
        st_off = 0
        for i in range(len(self.btm_names)):
            to_btm[self.btm_names[i]]  = owl.slice(from_top[self.top_names[0]], self.concat_dim, st_off, self.slice_count[i])
            st_off += self.slice_count[i]
    def __str__(self):
        return 'concat'

class FullyConnection(WeightedComputeUnit):
    def __init__(self, params):
        super(FullyConnection, self).__init__(params)
        self.inner_product_param = params.inner_product_param

    def ff(self, act, phase):
        shp = act.shape
        if len(shp) > 2:
            a = act.reshape([np.prod(shp[0:-1], dtype=np.int32), shp[-1]])
        else:
            a = act
        self.ff_act = act # save ff value
        return self.weight * a + self.bias
    def bp(self, sen):
        shp = self.ff_act.shape
        if len(shp) > 2:
            a = self.ff_act.reshape([np.prod(shp[0:-1], dtype=np.int32), shp[-1]])
        else:
            a = self.ff_act

        self.weightgrad = sen * a.trans()
        self.biasgrad = sen.sum(1)
        s = self.weight.trans() * sen
        if len(shp) > 2:
            s = s.reshape(shp)
        return s
    def __str__(self):
        return 'fc'

class ConvConnection(WeightedComputeUnit):
    def __init__(self, params):
        super(ConvConnection, self).__init__(params)
        self.conv_params = params.convolution_param
        self.convolver = co.Convolver(self.conv_params.pad,
                self.conv_params.pad, self.conv_params.stride, self.conv_params.stride)
        self.convolution_param = params.convolution_param
        self.num_output = params.convolution_param.num_output
        self.group = params.convolution_param.group
        #TODO: hack, we don't want to slice agian to use it into bp as a parameter
        self.group_data = []
        self.group_filter = []
        self.group_bias = []
    def ff(self, act, phase):
        if self.group == 1:
            self.ff_act = act
            return self.convolver.ff(act, self.weight, self.bias)
        else:
            #slice data
            self.group_data = []
            group_result = []
            self.group_filter = []
            self.group_bias = []

            data_concat_dim = 2
            filter_concat_dim = 3
            bias_concat_dim = 0
            data_slice_count = act.shape[data_concat_dim] / self.group
            filter_slice_count = self.weight.shape[filter_concat_dim] / self.group
            for i in xrange(self.group):
                self.group_data.append(owl.slice(act, data_concat_dim, data_slice_count * i, data_slice_count))
                self.group_filter.append(owl.slice(self.weight, filter_concat_dim, filter_slice_count * i, filter_slice_count))
                self.group_bias.append(owl.slice(self.bias, bias_concat_dim, filter_slice_count * i, filter_slice_count))
                group_result.append(self.convolver.ff(self.group_data[i], self.group_filter[i], self.group_bias[i]))
            #concat
            return owl.concat(group_result, data_concat_dim)

    def bp(self, sen):
        if self.group == 1:
            self.weightgrad = self.convolver.weight_grad(sen, self.ff_act, self.weight)
            self.biasgrad = self.convolver.bias_grad(sen)
            return self.convolver.bp(sen, self.ff_act, self.weight)
        else:
            #slice data
            group_sen = []
            group_wgrad = []
            group_bgrad = []
            group_result = []

            data_concat_dim = 2
            filter_concat_dim = 3
            bias_concat_dim = 0
            data_slice_count = sen.shape[data_concat_dim] / self.group
            filter_slice_count = self.weight.shape[filter_concat_dim] / self.group
            for i in xrange(self.group):
                group_sen.append(owl.slice(sen, data_concat_dim, data_slice_count * i, data_slice_count))
                group_wgrad.append(self.convolver.weight_grad(group_sen[i], self.group_data[i], self.group_filter[i]))
                group_bgrad.append(self.convolver.bias_grad(group_sen[i]))
                group_result.append(self.convolver.bp(group_sen[i], self.group_data[i], self.group_filter[i]))
            #concat
            self.weightgrad = owl.concat(group_wgrad, filter_concat_dim)
            self.biasgrad = owl.concat(group_bgrad, bias_concat_dim)

            #free space
            self.group_data = []
            self.group_filter = []
            self.group_bias = []
            return owl.concat(group_result, data_concat_dim)

    def __str__(self):
        return 'conv'

class DataUnit(ComputeUnit):
    def __init__(self, params, num_gpu):
        super(DataUnit, self).__init__(params)
        self.crop_size = params.transform_param.crop_size
        self.num_output = 3
        self.mirror = params.transform_param.mirror
        if params.include[0].phase == Phase.Value('TRAIN'):
            self.dp = ImageNetDataProvider(params.transform_param.mean_file, params.transform_param.mean_value,
                    params.data_param.source,
                    params.data_param.batch_size / num_gpu,
                    params.transform_param.crop_size)
        else:
            self.dp = ImageNetDataProvider(params.transform_param.mean_file, params.transform_param.mean_value,
                    params.data_param.source,
                    params.data_param.batch_size,
                    params.transform_param.crop_size)

        self.generator = None
        #(self.samples, self.labels) = next(self.generator)

    def forward(self, from_btm, to_top, phase):
        if self.generator == None:
            self.generator = self.dp.get_train_mb(self.mirror, phase)

        while True:
            try:
                (samples, labels) = next(self.generator)
                if len(labels) == 0:
                    (samples, labels) = next(self.generator)
            except StopIteration:
                print 'Have scanned the whole dataset; start from the begginning agin'
                self.generator = self.dp.get_train_mb(self.mirror, phase)
                continue
            break

        to_top[self.top_names[0]] = owl.from_numpy(samples).reshape([self.crop_size, self.crop_size, 3, samples.shape[0]])
        to_top[self.top_names[1]] = owl.from_numpy(labels)
        '''
        to_top[self.top_names[0]] = owl.from_numpy(self.samples).reshape([self.crop_size, self.crop_size, 3, self.samples.shape[0]])
        to_top[self.top_names[1]] = owl.from_numpy(self.labels)
        '''

    def backward(self, from_top, to_btm, phase):
        pass
    def __str__(self):
        return 'data'

class Net:
    def __init__(self):
        self.units = []
        self.adjacent = []
        self.reverse_adjacent = []
        self.base_lr = 0
        self.base_weight_decay = 0
        self.momentum = 0
        self.name_to_uid = {}
        self.loss_uids = []
        self.accuracy_uids = []

    def add_unit(self, unit):
        uid = len(self.units)
        self.units.append(unit)
        self.adjacent.append([])
        self.reverse_adjacent.append([])
        if not unit.name in self.name_to_uid:
            self.name_to_uid[unit.name] = []
        self.name_to_uid[unit.name].append(uid)
        return uid

    def get_units_by_name(self, name):
        return [self.units[uid] for uid in self.name_to_uid[name]]

    def get_loss_units(self):
        return [self.units[uid] for uid in self.loss_uids]

    def get_accuracy_units(self):
        return [self.units[uid] for uid in self.accuracy_uids]

    def get_data_unit(self, phase = 'TRAIN'):
        data_units = self.name_to_uid['data']
        for du in data_units:
            if not self._is_excluded(du, phase):
                return self.units[du]

    def get_weighted_unit_ids(self):
        weights_id = []
        for i in xrange(len(self.units)):
            if isinstance(self.units[i], WeightedComputeUnit):
                weights_id.append(i)
        return weights_id

    def connect(self, u1, u2):
        self.adjacent[u1].append(u2)
        self.reverse_adjacent[u2].append(u1)

    def _is_excluded(self, unit, phase):
        p = self.units[unit].params
        return phase != None and len(p.include) != 0 and p.include[0].phase != Phase.Value(phase)

    def _toporder(self, phase = None):
        depcount = [len(inunits) for inunits in self.reverse_adjacent]
        queue = Queue.Queue()
        # remove dep from excluded units
        for unit in range(len(depcount)):
            if self._is_excluded(unit, phase):
                for l in self.adjacent[unit]:
                    depcount[l] -= 1
        # find start units
        for unit in range(len(depcount)):
            count = depcount[unit]
            if count == 0:
                queue.put(unit)
        # run
        while not queue.empty():
            unit = queue.get()
            if self._is_excluded(unit, phase):
                continue
            yield unit
            for l in self.adjacent[unit]:
                depcount[l] -= 1
                if depcount[l] == 0:
                    queue.put(l)

    def _reverse_toporder(self, phase = None):
        depcount = [len(outunits) for outunits in self.adjacent]
        queue = Queue.Queue()
        # remove dep from excluded units
        for unit in range(len(depcount)):
            if self._is_excluded(unit, phase):
                for l in self.reverse_adjacent[unit]:
                    depcount[l] -= 1
        # find start units
        for unit in range(len(depcount)):
            count = depcount[unit]
            if count == 0:
                queue.put(unit)
        # run
        while not queue.empty():
            unit = queue.get()
            if self._is_excluded(unit, phase):
                continue
            yield unit
            for l in self.reverse_adjacent[unit]:
                depcount[l] -= 1
                if depcount[l] == 0:
                    queue.put(l)

    def forward(self, phase = 'TRAIN'):
        unit_to_tops = [{} for name in self.units]
        for u in self._toporder(phase):
            from_btm = {}
            for btm in self.reverse_adjacent[u]:
                from_btm.update(unit_to_tops[btm])
            self.units[u].forward(from_btm, unit_to_tops[u], phase)

    def backward(self, phase = 'TRAIN'):
        unit_to_btms = [{} for name in self.units]
        for u in self._reverse_toporder(phase):
            from_top = {}
            for top in self.adjacent[u]:
                for keys in unit_to_btms[top]:
                    if keys in from_top:
                        from_top[keys] += unit_to_btms[top][keys]
                    else:
                        from_top[keys] = unit_to_btms[top][keys]
            self.units[u].backward(from_top, unit_to_btms[u], phase)

    def update(self, uid):
        self.units[uid].weight_update(self.current_lr, self.base_weight_decay, self.momentum, self.batch_size)

    def weight_update(self, num_gpu):
        for i in range(len(self.units)):
            update(i, num_gpu)

    def wait_for_eval_loss(self):
        self.get_loss_units()[0].ff_y.wait_for_eval()

    def __str__(self):
        ret = 'digraph G {\n'
        for uid in range(len(self.units)):
            ret += 'n' + str(uid) + ' [label="' + self.units[uid].name + '"]\n'
        for uid in range(len(self.units)):
            for nuid in self.adjacent[uid]:
                ret += 'n' + str(uid) + ' -> n' + str(nuid) + '\n'
        return ret + '}\n'
