from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer, DataCollatorForLanguageModeling
from peft import LoraConfig, get_peft_model

# 1️⃣ Temel model (bilgili, Türkçe anlayan)
model_name = "mistralai/Mistral-7B-Instruct-v0.2"

# 2️⃣ Dataset yükle
dataset = load_dataset("json", data_files="adana_tuning.jsonl", split="train")

# 3️⃣ Tokenizer ve model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, load_in_8bit=True, device_map="auto")

# 4️⃣ LoRA yapılandırması
lora_config = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj","v_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM"
)
model = get_peft_model(model, lora_config)

# 5️⃣ Eğitim ayarları
training_args = TrainingArguments(
    output_dir="./adanali_mistral_lora",
    per_device_train_batch_size=1,
    gradient_accumulation_steps=16,
    num_train_epochs=2,
    learning_rate=1e-5,
    fp16=True,
    logging_steps=10,
    save_strategy="epoch",
    report_to="none"
)

# 6️⃣ Trainer başlat
trainer = Trainer(
    model=model,
    args=training_args,
    train_dataset=dataset,
    data_collator=DataCollatorForLanguageModeling(tokenizer, mlm=False)
)

trainer.train()
model.save_pretrained("./adanali_mistral_lora")
print("\n✅ Eğitim tamamlandı! Model 'adanali_mistral_lora/' klasörüne kaydedildi.")
