# -*- coding: utf-8 -*-
import torch  # 用于搭建及训练模型
from torchtext import data  # 用于生成数据集
from torchtext.vocab import Vectors  # 用于载入预训练词向量
from torchtext.data import BucketIterator  # 用于生成训练和测试所用的迭代器
import os.path as path
import codecs 
from gensim.models import Word2Vec, KeyedVectors
from sklearn.cluster import KMeans # 聚类函数

def tokenize(x): return x.split()

#在这里修改加载文件的位置
wordvecPath = "word2vec7.vector"
dataPath = "../data/"
TEXT = data.Field(sequential=True, tokenize=tokenize)
wordVec = KeyedVectors.load_word2vec_format(wordvecPath, binary = False)
vocab = wordVec.vocab

# 加载数据集所用类与函数
class Dataset(data.Dataset):
    name = 'Dataset'
    def __init__(self, fin, text_field):
        fields = [("text", text_field)]
        examples = []
        print('read data from {}'.format(path))
        for line in fin:
            examples.append(data.Example.fromlist([line], fields))
        super(Dataset, self).__init__(examples, fields) # 生成标准dataset
        
def getDataIter(fin, fiveOrSeven, batch_size):
    data = Dataset(fin, TEXT)
    vectors = Vectors(wordvecPath)
    TEXT.build_vocab(data, vectors=vectors, unk_init = torch.Tensor.normal_) # 构建映射
    return BucketIterator(dataset=data, batch_size=batch_size, shuffle=True)

def getTrainIter(fiveOrSeven, batch_size):
    assert fiveOrSeven == 5 or fiveOrSeven == 7
    trainfin = codecs.open(path.join(dataPath, "qtrain"+str(fiveOrSeven)), 'r', encoding = 'utf-8')
    return getDataIter(trainfin, fiveOrSeven, batch_size)

def getTestIter(fiveOrSeven, batch_size):
    assert fiveOrSeven == 5 or fiveOrSeven == 7
    testfin = codecs.open(path.join(dataPath, "qtest"+str(fiveOrSeven)), 'r', encoding = 'utf-8')
    return getDataIter(testfin, fiveOrSeven, batch_size)

def getValidIter(fiveOrSeven, batch_size):
    assert fiveOrSeven == 5 or fiveOrSeven == 7
    validfin = codecs.open(path.join(dataPath, "qvalid"+str(fiveOrSeven)), 'r', encoding = 'utf-8')
    return getDataIter(validfin, fiveOrSeven, batch_size)

# 获取一个batch的单字的onehot向量组成的矩阵
def idx_to_onehot(w, vocab_size, batch_size):
    res = torch.zeros((batch_size, vocab_size)).cuda().scatter(1, w, 1)
    return torch.transpose(res,0,1)

def itos(idx):
    result = torch.zeros((idx.size()), dtype=torch.long)
    for a, i in enumerate(idx):
        result[a] = int(TEXT.vocab.itos[i])
    return result

# 计算预测结果与真实结果相同字的个数
def calSame(out, real):
    return int(torch.argmax(out,dim=1).eq(real).sum())

# 梯度裁剪
def clip_gradient(optimizer, grad_clip):
    """
    Clips gradients computed during backpropagation to avoid explosion of gradients.

    :param optimizer: optimizer with the gradients to be clipped
    :param grad_clip: clip value
    """
    for group in optimizer.param_groups:
        for param in group["params"]:
            if param.grad is not None:
                param.grad.data.clamp_(-grad_clip, grad_clip)
                
# 聚类函数 将文件中的字进行聚类存到字典中
""" params: n if number of clusters, path is the path of train file
    return: res -> {character:(label, probability)}
    using KMeans cluster
"""
def cluster(n, path):
    trainfin = codecs.open(path, 'r', encoding = 'utf-8')
    wordscnt = {}
    for line in trainfin:
        for c in line.split():
            wordscnt[c] = wordscnt.get(c, 0) + 1
    words = []
    buffer = []
    for c in wordscnt.keys():
        if c in vocab:
            words.append(c)
        else:
            buffer.append(c)
    vectors = [wordVec[c] for c in words]
    clt = KMeans(n-1)
    clt.fit(vectors)
    freq = [0]*n
    for i in range(len(words)):
        freq[clt.labels_[i]] += wordscnt[words[i]]
    for c in buffer:
        freq[n-1] += wordscnt[c]
    res = {}
    for i in range(len(words)):
        c = words[i]
        label = clt.labels_[i]
        prob = wordscnt[c] / freq[label]
        res[c] = tuple((label, prob))
    for c in buffer:
        prob = wordscnt[c] / freq[label]
        res[c] = tuple((n-1, prob))
    return res