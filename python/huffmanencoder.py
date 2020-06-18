from collections import defaultdict
import heapq

# A custom static Huffman-encoder variant.


class Node(object):
    def __init__(self, value=None, ch0=None, ch1=None):
        self.value = value
        self.parent = None
        if value is not None:
            self.rank = 1
        else:
            r0 = ch0.rank
            r1 = ch1.rank
            if r0 < r1:
                ch0, ch1 = ch1, ch0
            self.rank = max(r0, r1) + 1
            ch0.parent = self
            ch1.parent = self
        self.ch0 = ch0
        self.ch1 = ch1

    def __repr__(self):
        if self.value is not None:
            return "[%d]" % self.value
        return "'%s'" % ('' if not hasattr(self, 'code') else self.code)

def archive(dictfile, datafile, input):
    freqcount = defaultdict(int)

    for b in input:
        freqcount[b] += 1

    for end_token in range(256):
        if end_token not in freqcount:
            freqcount[end_token] = 0
            break
    ok = False
    for null_token in range(256):
        if null_token not in freqcount:
            ok = True
            break
    assert ok

    flist = [(freqcount[b], 1, Node(value=b)) for b in freqcount]
    heapq.heapify(flist)

    while len(flist) > 1:
        fr0, r0, n0 = heapq.heappop(flist)
        fr1, r1, n1 = heapq.heappop(flist)
        n2 = Node(ch0=n0, ch1=n1)
        heapq.heappush(flist, (fr0 + fr1, n2.rank, n2))

    root = flist[0][2]

    dictpart = [end_token]
    treemodel = defaultdict(lambda: null_token)

    root.code = ""

    opers = [("", root)]

    char2bitstring = dict()

    node_positions = {}

    pt_inds = []
    while opers:
        prefix, n = opers.pop()
        n.code = prefix
        node_positions[n.code] = len(pt_inds)
        # Compute my_ind.
        base = sum([0] + [2 ** i for i in range(len(prefix))])
        my_ind = base + (1 if not prefix else 1 + int(prefix, 2))
        if n.value is not None:
            treemodel[my_ind] = n.value
            char2bitstring[n.value] = prefix
            pt_inds.extend([n.value, 0])
        else:
            treemodel[my_ind] = null_token
            opers.extend([(prefix + "0", n.ch0), (prefix + "1", n.ch1)])
            pt_inds.extend([n.ch0, n.ch1])

    dictpart.extend(treemodel[k] for k in range(max(treemodel.keys()) + 1))

    altdict = pt_inds[:]

    for i, n in enumerate(pt_inds):
        if isinstance(n, Node):
            altdict[i] = node_positions[n.code] - i + (i % 2)

    total_string = "".join(char2bitstring[c] for c in input) + char2bitstring[end_token]

    total_string = total_string + "0" * (8 - len(total_string) % 8)
    datapart = []
    for i in range(0, len(total_string), 8):
        v = "".join(reversed(total_string[i:(i+8)]))
        datapart.append(int(v, 2))

    altdict = [end_token] + altdict

    with open(dictfile, 'wb') as f:
        output = bytearray(altdict)
        f.write(output)

    with open(datafile, 'wb') as f:
        output = bytearray(datapart)
        f.write(output)


def create_dictionary(input):
    freqcount = defaultdict(int)

    for b in input:
        freqcount[b] += 1

    for end_token in range(256):
        if end_token not in freqcount:
            freqcount[end_token] = 0
            break
    ok = False
    for null_token in range(256):
        if null_token not in freqcount:
            ok = True
            break
    assert ok  # Code tree failed or would need an escape character.

    flist = [(freqcount[b], 1, b, Node(value=b)) for b in freqcount]
    flist.sort()

    heapq.heapify(flist)

    while len(flist) > 1:
        fr0, r0, _, n0 = heapq.heappop(flist)
        fr1, r1, _, n1 = heapq.heappop(flist)
        n2 = Node(ch0=n0, ch1=n1)
        heapq.heappush(flist, (fr0 + fr1, n2.rank, _, n2))

    root = flist[0][3]

    dictpart = [end_token]
    treemodel = defaultdict(lambda: null_token)

    root.code = ""

    opers = [("", root)]

    char2bitstring = dict()

    node_positions = {}

    pt_inds = []
    while opers:
        prefix, n = opers.pop()
        n.code = prefix
        node_positions[n.code] = len(pt_inds)
        # Compute my_ind.
        base = sum([0] + [2 ** i for i in range(len(prefix))])
        my_ind = base + (1 if not prefix else 1 + int(prefix, 2))
        if n.value is not None:
            treemodel[my_ind] = n.value
            char2bitstring[n.value] = prefix
            pt_inds.extend([n.value, 0])
        else:
            treemodel[my_ind] = null_token
            opers.extend([(prefix + "0", n.ch0), (prefix + "1", n.ch1)])
            pt_inds.extend([n.ch0, n.ch1])

    dictpart.extend(treemodel[k] for k in range(max(treemodel.keys()) + 1))

    altdict = pt_inds[:]

    for i, n in enumerate(pt_inds):
        if isinstance(n, Node):
            altdict[i] = node_positions[n.code] - i + (i % 2)

    return {"altdict": altdict, "char2bitstring": char2bitstring,
            "end_token": end_token}


def write_dictionary(dictionary, fname):
    altdict = dictionary['altdict']
    end_token = dictionary['end_token']
    altdict = [end_token] + altdict

    with open(fname, 'wb') as f:
        output = bytearray(altdict)
        f.write(output)


def create_compressed_array(dictionary, input):
    char2bitstring = dictionary['char2bitstring']
    altdict = dictionary['altdict']
    end_token = dictionary['end_token']
    total_string = "".join(char2bitstring[c] for c in input) + char2bitstring[end_token]

    if len(total_string) % 8 != 0:
        total_string = total_string + "0" * (8 - len(total_string) % 8)
    datapart = []
    for i in range(0, len(total_string), 8):
        v = "".join(reversed(total_string[i:(i + 8)]))
        datapart.append(int(v, 2))
    return datapart


def create_archive(dictionary, input, fname):
    char2bitstring = dictionary['char2bitstring']
    altdict = dictionary['altdict']
    end_token = dictionary['end_token']
    total_string = "".join(char2bitstring[c] for c in input) + char2bitstring[end_token]

    if len(total_string) % 8 != 0:
        total_string = total_string + "0" * (8 - len(total_string) % 8)
    datapart = []
    for i in range(0, len(total_string), 8):
        v = "".join(reversed(total_string[i:(i + 8)]))
        datapart.append(int(v, 2))

    with open(fname, 'wb') as f:
        output = bytearray(datapart)
        f.write(output)


"""
Current code dictionary format: all nodes are 2 bytes.
If second byte == 0, then the first byte is the value of this leaf node.
Otherwise, the child leaves are at [first byte addr] + the first/second byte.
"""
