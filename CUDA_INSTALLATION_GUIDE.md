# راهنمای نصب CUDA برای SubFarsiPro

## 📖 CUDA چیست؟

**CUDA** (Compute Unified Device Architecture) یک پلتفرم محاسبات موازی از NVIDIA است که به برنامه‌ها اجازه می‌دهد از GPU برای شتاب‌دهی استفاده کنند.

### چرا CUDA مهم است؟

- **بدون CUDA**: Whisper روی CPU اجرا می‌شود (کند اما کار می‌کند)
- **با CUDA**: Whisper روی GPU اجرا می‌شود (10-50 برابر سریع‌تر!)

## 🔍 بررسی GPU

قبل از نصب CUDA، بررسی کنید که GPU NVIDIA دارید:

```bash
nvidia-smi
```

اگر اطلاعات GPU را دیدید → GPU NVIDIA دارید ✅
اگر خطا داد → GPU NVIDIA ندارید (از CPU mode استفاده کنید)

## 📦 نصب CUDA (Linux)

### روش 1: نصب از طریق Package Manager (Ubuntu/Debian)

```bash
# به‌روزرسانی سیستم
sudo apt update

# نصب CUDA Toolkit 12.1
wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-keyring_1.1-1_all.deb
sudo dpkg -i cuda-keyring_1.1-1_all.deb
sudo apt-get update
sudo apt-get -y install cuda-toolkit-12-1

# اضافه کردن به PATH
echo 'export PATH=/usr/local/cuda-12.1/bin${PATH:+:${PATH}}' >> ~/.bashrc
echo 'export LD_LIBRARY_PATH=/usr/local/cuda-12.1/lib64${LD_LIBRARY_PATH:+:${LD_LIBRARY_PATH}}' >> ~/.bashrc
source ~/.bashrc
```

### روش 2: نصب از طریق NVIDIA Website

1. به https://developer.nvidia.com/cuda-downloads بروید
2. سیستم عامل خود را انتخاب کنید (Linux)
3. نسخه مناسب را دانلود کنید (CUDA 11.8 یا 12.1)
4. دستورالعمل‌های نصب را دنبال کنید

## 📦 نصب PyTorch با پشتیبانی CUDA

بعد از نصب CUDA Toolkit، باید PyTorch را با پشتیبانی CUDA نصب کنید:

### برای CUDA 11.8:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
```

### برای CUDA 12.1:
```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

### برای CPU فقط (بدون CUDA):
```bash
pip install torch torchvision torchaudio
```

## ✅ بررسی نصب

برای بررسی اینکه CUDA به درستی نصب شده:

```bash
# بررسی CUDA
nvcc --version

# بررسی PyTorch CUDA
python -c "import torch; print('CUDA Available:', torch.cuda.is_available()); print('CUDA Version:', torch.version.cuda if torch.cuda.is_available() else 'N/A')"
```

اگر `CUDA Available: True` را دیدید → نصب موفق بوده! ✅

## 🐛 حل مشکلات رایج

### مشکل 1: `nvidia-smi` کار نمی‌کند
- بررسی کنید که درایور NVIDIA نصب باشد
- `sudo apt install nvidia-driver-535` (یا نسخه جدیدتر)

### مشکل 2: PyTorch CUDA را پیدا نمی‌کند
- مطمئن شوید که نسخه CUDA Toolkit با نسخه PyTorch CUDA سازگار است
- PyTorch را دوباره نصب کنید با نسخه صحیح CUDA

### مشکل 3: Out of Memory (OOM)
- از مدل کوچک‌تر Whisper استفاده کنید (base یا tiny)
- یا از CPU mode استفاده کنید

## 💡 نکات مهم

1. **CUDA اختیاری است**: برنامه بدون CUDA هم کار می‌کند (فقط کندتر)
2. **GPU Memory**: اگر VRAM کم دارید (< 4GB)، از مدل `base` استفاده کنید
3. **CPU Mode**: همیشه می‌توانید از CPU استفاده کنید (گزینه 3 در تنظیمات Whisper)

## 🔗 لینک‌های مفید

- [CUDA Downloads](https://developer.nvidia.com/cuda-downloads)
- [PyTorch Installation](https://pytorch.org/get-started/locally/)
- [NVIDIA Drivers](https://www.nvidia.com/Download/index.aspx)

