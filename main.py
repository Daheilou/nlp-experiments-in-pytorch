from __future__ import print_function

import datetime
import os

import torch

from datahelper.dataset_reader import DatasetLoader
from datahelper.embedding_helper import OOVEmbeddingCreator
from datahelper.preprocessor import Preprocessor
from evaluation.evaluator import Evaluator
from models.CNN import TextCnn, CharCNN, VDCNN, ConvDeconvCNN
from models.GRU import GRU
from models.LSTM import LSTM
from training.trainer import Trainer
from utils.utils import save_vocabulary

dataset_properties = {"stop_word_path": "D:/Anaconda3/nltk_data/corpora/stopwords/english",
                      # "stop_word_path": "D:/nlpdata/stopwords/turkish",
                      # "data_path": "D:/nlpdata/tr_test.DUMP",
                      "data_path": "D:/PyTorchNLP/data/EWNERTC_TC_Coarse Grained NER_No_NoiseReduction.DUMP",
                      "embedding_vector": "fasttext.en.300d",
                      # "vector_cache": "D:/nlpdata/fasttext",
                      "vector_cache": "D:/PyTorchNLP/data/fasttext",
                      # "pretrained_embedding_path": "D:/nlpdata/fasttext/wiki.tr",
                      "pretrained_embedding_path": "D:/PyTorchNLP/data/fasttext/wiki.en",
                      # "data_path": "D:/PyTorchNLP/data/EWNERTC_TC_Coarse Grained NER_No_NoiseReduction.DUMP",
                      # "embedding_vector": "fasttext.en.300d",
                      # "vector_cache": "D:/PyTorchNLP/data/fasttext",
                      # "pretrained_embedding_path": "D:/PyTorchNLP/data/fasttext/wiki.en",
                      "checkpoint_path": "",
                      "saved_sentence_vocab": "D:/PyTorchNLP/saved/vocab/category_vocab.dat",
                      "saved_category_vocab": "D:/PyTorchNLP/saved/vocab/sentence_vocab.dat",
                      "oov_embedding_type": "fasttext_oov",
                      "batch_size": 32
                      }

model_properties = {"use_pretrained_embed": True,
                    "embed_train_type": "static",
                    "use_padded_conv": True,
                    "dropout_type": "bernoulli",
                    "keep_prob": 0.5,
                    "use_batch_norm": True,
                    "batch_norm_momentum": 0.1,
                    "batch_norm_affine": False,
                    # ShallowCNN (Single Layer) related parameters
                    "filter_count": 64,
                    "filter_sizes": [3, 4, 5],
                    # CharCNN related parameters
                    "max_sequence_length": 1014,
                    "feature_size": "large",
                    "charcnn_filter_count": 1024,
                    "charcnn_filter_sizes": [7, 7, 3, 3, 3, 3],
                    "max_pool_kernels": [3, 3, 3],
                    "linear_unit_count": 2048,
                    # VDCNN related parameters
                    "depth": 9,
                    "vdcnn_filter_counts": [64, 128, 256, 512],
                    "vdcnn_filter_size": 3,
                    "use_shortcut": True,
                    "downsampling_type": "resnet",
                    "maxpool_filter_size": 3,
                    "kmax": 8,
                    # Conv-Deconv related parameters
                    "encodercnn_filter_counts": [300, 600, 500],
                    "encodercnn_filter_sizes": [5, 5, 12],
                    "encodercnn_strides": [2, 2, 1],
                    "deconv_temperature": 0.01,
                    "conv_deconv_hidden_layer_size": 500,
                    # RNN-GRU-LSTM related parameters
                    "rnn_hidden_dim": 300,
                    "rnn_num_layers": 1,
                    "rnn_bidirectional": False,
                    "rnn_bias": True,
                    # Run mode parameter
                    # "run_mode": "eval_interactive",
                    "run_mode": "train",
                    }

training_properties = {"learner": "textcnn",
                       "optimizer": "Adam",
                       "learning_rate": 0.05,
                       "weight_decay": 0,
                       "momentum": 0.9,
                       "norm_ratio": 0.25,
                       "epoch": 20,
                       "print_every_batch_step": 250,
                       "save_every_epoch": 1,
                       "topk": (5, 1),
                       "eval_every": 1,
                       }

evaluation_properties = {"model_path": "D:/PyTorchNLP/saved/2018-12-06/",
                         "sentence_vocab": "D:/PyTorchNLP/saved/vocab/sentence_vocab.dat",
                         "category_vocab": "D:/PyTorchNLP/saved/vocab/category_vocab.dat"
                         }

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def initialize_model_and_trainer(model_properties, training_properties, datasetloader, device):
    model, trainer = None, None
    print("Model type is", training_properties["learner"])
    if training_properties["learner"] == "textcnn":
        model = TextCnn(model_properties).to(device)
        trainer = Trainer.trainer_factory("single_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
    elif training_properties["learner"] == "gru":
        model = GRU(model_properties).to(device)
        trainer = Trainer.trainer_factory("single_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
    elif training_properties["learner"] == "lstm":
        model = LSTM(model_properties).to(device)
        trainer = Trainer.trainer_factory("single_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
    elif training_properties["learner"] == "charcnn":
        model = CharCNN(model_properties).to(device)
        trainer = Trainer.trainer_factory("single_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
    elif training_properties["learner"] == "vdcnn":
        model = VDCNN(model_properties).to(device)
        trainer = Trainer.trainer_factory("single_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
    elif training_properties["learner"] == "conv-deconv-cnn":
        convDeconveCNN = ConvDeconvCNN(model_properties)
        encoderCNN = convDeconveCNN.encoder.to(device)
        decoderCNN = convDeconveCNN.decoder.to(device)
        classifier = convDeconveCNN.classifier.to(device)
        trainer = Trainer.trainer_factory("multiple_model_trainer", training_properties, datasetloader.train_iter,
                                          datasetloader.val_iter, datasetloader.test_iter, device)
        model = [encoderCNN, decoderCNN, classifier]
    else:
        raise ValueError("Model is not defined!")

    return model, trainer


if __name__ == '__main__':
    assert model_properties["run_mode"] == "train" or \
           model_properties["run_mode"] == "eval_interactive"

    print("Initial device is", device)
    if "cuda" == device:
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.fastest = True
    else:
        torch.set_num_threads(8)
        torch.backends.cudnn.enabled = False

    stop_word_path = dataset_properties["stop_word_path"]
    data_path = dataset_properties["data_path"]
    vector_cache = dataset_properties["vector_cache"]
    fasttext_model_path = dataset_properties["pretrained_embedding_path"]

    oov_embedding_type = dataset_properties["oov_embedding_type"]
    batch_size = dataset_properties["batch_size"]

    embedding_vector = dataset_properties["embedding_vector"]

    save_dir = os.path.abspath(os.path.join(os.curdir, "saved", datetime.datetime.today().strftime('%Y-%m-%d')))
    save_dir_vocab = os.path.abspath(os.path.join(os.curdir, "saved", "vocab"))
    if not os.path.isdir(save_dir):
        os.makedirs(save_dir)
    if not os.path.isdir(save_dir_vocab):
        os.makedirs(save_dir_vocab)
    print("Saving directory for models is", save_dir)
    print("Saving directory for vocabulary files is", save_dir_vocab)
    training_properties["save_path"] = save_dir

    level = "word"
    is_char_level = False
    if training_properties["learner"] == "charcnn" or training_properties["learner"] == "vdcnn":
        print("Caution: Due to selected learning model, everything will be executed in character-level!")
        level = "char"
        is_char_level = True

    print("Initialize Preprocessor")
    preprocessor = Preprocessor(stop_word_path,
                                is_remove_digit=True,
                                is_remove_punctuations=False,
                                is_char_level=is_char_level)

    if model_properties["run_mode"] == "train":
        print("Initialize OOVEmbeddingCreator")
        unkembedding = OOVEmbeddingCreator(type=oov_embedding_type,
                                           fasttext_model_path=fasttext_model_path)

        print("Initialize DatasetLoader")
        datasetloader = DatasetLoader(data_path=data_path,
                                      vector=embedding_vector,
                                      preprocessor=preprocessor.preprocess,
                                      level=level,
                                      vector_cache=vector_cache,
                                      unk_init=unkembedding.create_oov_embedding)

        print("Loading train, validation and test sets")
        train, val, test = datasetloader.read_dataset(batch_size=batch_size)
        print("Loading vocabularies")
        sentence_vocab = datasetloader.sentence_vocab
        category_vocab = datasetloader.category_vocab
        print("Loading embeddings")
        pretrained_embeddings = datasetloader.sentence_vocab_vectors
        print("Updating properties")
        model_properties["device"] = device

        if training_properties["learner"] == "charcnn":
            model_properties["vocab_size"] = len(sentence_vocab)
            model_properties["embed_dim"] = len(sentence_vocab) - 1
        elif training_properties["learner"] == "vdcnn":
            model_properties["vocab_size"] = len(sentence_vocab)
            model_properties["embed_dim"] = 16
        else:
            model_properties["vocab_size"] = pretrained_embeddings.size()[0]
            model_properties["embed_dim"] = pretrained_embeddings.size()[1]

        model_properties["num_class"] = len(category_vocab)
        model_properties["vocab"] = sentence_vocab
        model_properties["padding_id"] = sentence_vocab.stoi["<pad>"]
        model_properties["pretrained_weights"] = pretrained_embeddings
        model_properties["batch_size"] = dataset_properties["batch_size"]

        print("Saving vocabulary files")
        save_vocabulary(sentence_vocab, os.path.abspath(os.path.join(save_dir_vocab, "sentence_vocab.dat")))
        save_vocabulary(category_vocab, os.path.abspath(os.path.join(save_dir_vocab, "category_vocab.dat")))

        print("Initialize model and trainer")
        model, trainer = initialize_model_and_trainer(model_properties, training_properties, datasetloader, device)

        if dataset_properties["checkpoint_path"] is None or dataset_properties["checkpoint_path"] == "":
            print("Train process is starting from scratch!")
            trainer.train_iters(model)
        else:
            checkpoint = torch.load(dataset_properties["checkpoint_path"])
            print("Train process is reloading from epoch {}".format(checkpoint["epoch"]))
            trainer.train_iters(model, checkpoint)

    elif model_properties["run_mode"] == "eval_interactive":
        interactive_evaluator = Evaluator.evaluator_factory("interactive_evaluator", "cpu")

        model_path = evaluation_properties["model_path"]
        sentence_vocab_path = evaluation_properties["sentence_vocab"]
        category_vocab_path = evaluation_properties["category_vocab"]

        print("Interactive evaluation mode for model {}:".format(model_path))

        interactive_evaluator.evaluate_interactive(model_path=model_path,
                                                   sentence_vocab_path=sentence_vocab_path,
                                                   category_vocab_path=category_vocab_path,
                                                   preprocessor=preprocessor.preprocess,
                                                   topk=training_properties["topk"])
    print("")
