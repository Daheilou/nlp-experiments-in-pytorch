import torch

from utils.utils import calculate_accuracy, calculate_topk_accuracy, load_best_model


class SingleModelEvaluator(object):
    def __init__(self, device, is_vali):
        self.device = device
        self.is_vali = is_vali

    def evaluate_iter(self, model, input, criterion, save_path, topk):
        total_loss = 0
        total_acc = 0
        total_acc_topk = 0

        if not self.is_vali:
            print("Test mode!")
            model = load_best_model(save_path)
        else:
            print("Validation mode!")
        model.eval()

        with torch.no_grad():
            for batch in input:
                batch_x = batch.sentence.to(self.device)
                batch_y = batch.category_labels.to(self.device)

                predictions, _ = model(batch_x)

                loss = criterion(predictions, batch_y)
                accuracy = calculate_accuracy(predictions, batch_y)
                accuracy_topk = calculate_topk_accuracy(predictions, batch_y, topk=topk)

                total_loss += loss.item()
                total_acc += accuracy
                total_acc_topk += accuracy_topk[0].item()

                torch.cuda.empty_cache()

            current_loss = total_loss / len(input)
            current_acc = total_acc / len(input)
            current_acc_topk = total_acc_topk / len(input)

            return current_loss, current_acc, current_acc_topk
