import torch
import torch.nn as nn
import torch.nn.functional as F
from dropout_models.dropout import Dropout


class TextCnn(nn.Module):
    def __init__(self, args):
        super(TextCnn, self).__init__()
        self.args = args

        self.vocab = args["vocab"]

        # Device
        self.device = args["device"]

        # Input/Output dimensions
        embed_num = args["vocab_size"]
        embed_dim = args["embed_dim"]
        num_class = args["num_class"]

        # Embedding parameters
        padding_id = args["padding_id"]

        # Condition parameters
        use_pretrained_embed = args["use_pretrained_embed"]
        self.embed_train_type = args["embed_train_type"]
        use_padded_conv = args["use_padded_conv"]
        self.use_batch_norm = args["use_batch_norm"]

        # Pretrained embedding weights
        pretrained_weights = args["pretrained_weights"]

        # Dropout type
        self.dropout_type = args["dropout_type"]

        # Dropout probabilities
        keep_prob = args["keep_prob"]

        # Batch normalization parameters
        batch_norm_momentum = args["batch_norm_momentum"]
        batch_norm_affine = args["batch_norm_affine"]

        # Convolution parameters
        input_channel = 1
        filter_count = args["filter_count"]
        filter_sizes = args["filter_sizes"]

        # Embedding Layer Initialization
        print("> Embeddings")
        self.embed = nn.Embedding(num_embeddings=embed_num,
                                  embedding_dim=embed_dim,
                                  padding_idx=padding_id).cpu()

        # Create 2nd embedding layer for multichannel purpose
        if self.embed_train_type == "multichannel":
            self.embed_static = nn.Embedding(num_embeddings=embed_num,
                                             embedding_dim=embed_dim,
                                             padding_idx=padding_id).cpu()

        if use_pretrained_embed:
            print("> Pre-trained Embeddings")
            self.embed.from_pretrained(pretrained_weights)
            if self.embed_train_type == "multichannel":
                self.embed_static.from_pretrained(pretrained_weights)
        else:
            print("> Random Embeddings")
            random_embedding_weights = torch.rand(embed_num, embed_dim)
            self.embed.from_pretrained(random_embedding_weights)
            if self.embed_train_type == "multichannel":
                self.embed_static.from_pretrained(random_embedding_weights)

        if self.embed_train_type == "static":
            print("> Static Embeddings")
            self.embed.weight.requires_grad = False
        elif self.embed_train_type == "nonstatic":
            print("> Non-Static Embeddings")
            self.embed.weight.requires_grad = True
        elif self.embed_train_type == "multichannel":
            self.embed.weight.requires_grad = True
            self.embed_static.weight.requires_grad = False
        else:
            raise KeyError("Embedding train type can be (1) static, (2) nonstatic or (3) multichannel")

        # Convolution Initialization
        if use_padded_conv:
            print("> Padded convolution")
            self.convs = nn.ModuleList([nn.Conv2d(in_channels=input_channel,
                                                  out_channels=filter_count,
                                                  kernel_size=(filter_size, embed_dim),
                                                  stride=(1, 1),
                                                  padding=(filter_size // 2, 0),
                                                  bias=True) for filter_size in filter_sizes])
        else:
            print("> Without-pad convolution")
            self.convs = nn.ModuleList([nn.Conv2d(in_channels=input_channel,
                                                  out_channels=filter_count,
                                                  kernel_size=(filter_size, embed_dim),
                                                  bias=True) for filter_size in filter_sizes])

        num_flatten_feature = len(filter_sizes) * filter_count

        if self.dropout_type == "bernoulli" or self.dropout_type == "gaussian":
            print("> Dropout - ", self.dropout_type)
            self.dropout = Dropout(keep_prob=keep_prob, dimension=None, dropout_type=self.dropout_type).dropout
        elif self.dropout_type == "variational":
            print("> Dropout - ", self.dropout_type)
            self.dropout_before_flatten = Dropout(keep_prob=0.2, dimension=num_flatten_feature,
                                                  dropout_type=self.dropout_type).dropout
            self.dropout_fc1 = Dropout(keep_prob=keep_prob, dimension=num_flatten_feature // 2,
                                       dropout_type=self.dropout_type).dropout
        else:
            print("> Dropout - Bernoulli (You provide undefined dropout type!)")
            self.dropout = Dropout(keep_prob=keep_prob, dimension=None, dropout_type="bernoulli").dropout

        self.fc1 = nn.Linear(in_features=num_flatten_feature,
                             out_features=num_flatten_feature // 2,
                             bias=True)

        self.fc2 = nn.Linear(in_features=num_flatten_feature // 2,
                             out_features=num_class,
                             bias=True)

        if self.use_batch_norm:
            print("> Batch Normalization")
            self.convs_bn = nn.BatchNorm2d(num_features=filter_count,
                                           momentum=batch_norm_momentum,
                                           affine=batch_norm_affine)
            self.fc1_bn = nn.BatchNorm1d(num_features=num_flatten_feature // 2,
                                         momentum=batch_norm_momentum,
                                         affine=batch_norm_affine)
            self.fc2_bn = nn.BatchNorm1d(num_features=num_class,
                                         momentum=batch_norm_momentum,
                                         affine=batch_norm_affine)

    def forward(self, batch):
        kl_loss = torch.Tensor([0.0])
        # Input shape: [sentence_length, batch_size]
        batch_permuted = batch.permute(1, 0)
        # X shape: [batch_size, sentence_length]
        x = self.embed(batch_permuted)
        if self.embed_train_type == "multichannel":
            x_static = self.embed_static(batch_permuted)
            x = torch.stack[(x_static, x), 1]
        if "cuda" in str(self.device):
            x = x.cuda()
        # X shape: [batch_size, sentence_length, embedding_dim]
        x = x.unsqueeze(1)
        # X shape: [batch_size, 1, sentence_length, embedding_dim]
        if self.use_batch_norm:
            x = [self.convs_bn(F.relu(conv(x))).squeeze(3) for conv in self.convs]
        else:
            x = [F.relu(conv(x)).squeeze(3) for conv in self.convs]
        # X[i] shape: [batch_size, filter_count, sentence_lenght - filter_size[i]]
        x = [F.max_pool1d(conv, conv.size(2)).squeeze(2) for conv in x]
        # X[i] shape: [batch_size, filter_count]
        if self.dropout_type == "variational":
            x, kld = self.dropout_before_flatten(torch.cat(x, dim=1))
            kl_loss += kld.sum()
        else:
            x = self.dropout(torch.cat(x, dim=1))
        # Fully Connected Layers
        if self.use_batch_norm:
            if self.dropout_type == "variational":
                x, kld = self.dropout_fc1(self.fc1_bn(F.relu(self.fc1(x))))
                kl_loss += kld.sum()
            else:
                x = self.dropout(self.fc1_bn(F.relu(self.fc1(x))))
            x = self.fc2_bn(self.fc2(x))
        else:
            if self.dropout_type == "variational":
                x, kld = self.dropout_fc1(F.relu(self.fc1(x)))
                kl_loss += kld.sum()
            else:
                x = self.dropout(F.relu(self.fc1(x)))
            x = self.fc2(x)
        return x, kl_loss
