import torch
from transformers import GenerationConfig
from transformers.integrations import WandbCallback
import wandb
from tqdm.auto import tqdm


class LLMSampleCB(WandbCallback):
    def __init__(self, trainer, test_dataset, num_samples=10, max_new_tokens=256, log_model="checkpoint"):
        super().__init__()
        self._log_model = log_model
        self.sample_dataset = test_dataset.select(range(num_samples))
        self.model, self.tokenizer = trainer.model, trainer.tokenizer
        self.gen_config = GenerationConfig.from_pretrained(trainer.model.name_or_path, max_new_tokens=max_new_tokens)
        
    def generate(self, prompt):
        # tokenized_prompt = self.tokenizer(prompt, return_tensors='pt')['input_ids'].cuda()
        tokenized_prompt = self.tokenizer(prompt, return_tensors='pt')
        tokenized_prompt = {k: v.to("cuda") for k, v in tokenized_prompt.items()}

        with torch.inference_mode():
            output = self.model.generate(**tokenized_prompt, generation_config=self.gen_config, pad_token_id=self.tokenizer.eos_token_id)
            
        return self.tokenizer.decode(output[0][len(tokenized_prompt["input_ids"][0]):], skip_special_tokens=True)
    
    def samples_table(self, examples):
        records_table = wandb.Table(columns=["prompt", "generation"] + list(self.gen_config.to_dict().keys()))
        for example in tqdm(examples, leave=False):
            prompt = example["prompt"]
            generation = self.generate(prompt=prompt)
            records_table.add_data(prompt, generation, *list(self.gen_config.to_dict().values()))
        return records_table
        
    def on_evaluate(self, args, state, control,  **kwargs):
        super().on_evaluate(args, state, control, **kwargs)
        records_table = self.samples_table(self.sample_dataset)
        self._wandb.log({"sample_predictions":records_table})