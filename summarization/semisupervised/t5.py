import os
import json
import torch
import pickle
from tqdm import tqdm
from unidecode import unidecode
from malaya.text.rouge import postprocess_summary
import re

os.environ['CUDA_VISIBLE_DEVICES'] = '0'

# minimum cleaning, just simply to remove newlines.


def cleaning(string):
    string = string.replace('\n', ' ')
    string = re.sub(r'[ ]+', ' ', string).strip()
    return string


def postprocess(s, t):
    t = t.replace('£', 'RM')
    # return postprocess_summary(s, t)
    return t


minimum_len = 15


class Pointer:
    def __init__(self, filename):
        self.filename = filename
        self.index = 0

    def _save(self):
        with open(self.filename, 'wb') as fopen:
            pickle.dump(self.index, fopen)

    def increment(self):
        self.index += 1
        self._save()

    def load(self):
        if not os.path.exists(self.filename):
            return
        with open(self.filename, 'rb') as fopen:
            self.index = pickle.load(fopen)


filename = 'populate-news.json'
file = open(f'{filename}.semisupervised', 'a')

pointer = Pointer(f'{filename}.pickle')
pointer.load()
index = 0

data = []
with open(filename) as fopen:
    for line in fopen:
        if len(line):
            data.append(json.loads(line))

print(len(data))

from transformers import T5Tokenizer, T5ForConditionalGeneration

tokenizer = T5Tokenizer.from_pretrained('mesolitica/finetune-summarization-t5-base-standard-bahasa-cased')
model = T5ForConditionalGeneration.from_pretrained('mesolitica/finetune-summarization-t5-base-standard-bahasa-cased')
small_model = T5ForConditionalGeneration.from_pretrained(
    'mesolitica/finetune-summarization-t5-small-standard-bahasa-cased')

_ = model.cuda()
_ = small_model.cuda()

for i in tqdm(range(len(data))):
    if i >= pointer.index:
        torch.cuda.empty_cache()

        s = cleaning(data[i]['text'])
        input_ids = tokenizer.encode(f'ringkasan: {s}', return_tensors='pt').cuda()
        outputs = model.generate(input_ids,
                                 max_length=256)

        small_outputs = small_model.generate(input_ids,
                                             max_length=256)

        try:
            t = tokenizer.batch_decode(outputs, skip_special_tokens=True)
            t.extend(tokenizer.batch_decode(small_outputs, skip_special_tokens=True))
            t = [t_ for t_ in t if len(t_.split()) >= minimum_len]
            t = [postprocess(s, t_) for t_ in t]
            t = list(set(t))

            data[i]['semisupervised-summaries'] = t
            d = json.dumps(data[i])
            file.write(f'{d}\n')
            file.flush()
        except Exception as e:
            print(e)

        pointer.index = i
        pointer._save()
