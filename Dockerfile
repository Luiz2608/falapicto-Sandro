FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir ultralytics opencv-python-headless
# o build falha aqui se torch e torchvision não forem compatíveis (erro "torchvision::nms does not exist")
RUN python -c "import torch, torchvision; from torchvision.ops import nms; print(torch.__version__, torchvision.__version__, nms(torch.tensor([[0.,0.,10.,10.]]), torch.tensor([0.9]), 0.5))"
RUN apt-get update && apt-get install -y --no-install-recommends libxcb1 libgl1 libglib2.0-0 \
 && rm -rf /var/lib/apt/lists/*
COPY . .
ENV SLM_URL="" FALAPICTO_PROD=1
EXPOSE 8000
VOLUME /app/data
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
