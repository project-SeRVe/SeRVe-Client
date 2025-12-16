import ollama
from pathlib import Path

class VisionEngine:
    def __init__(self, model_name="llava"):
        self.model_name = model_name

    def analyze_image(self, image_bytes, prompt="Describe this image in detail."):
        """
        이미지 바이트와 프롬프트를 받아 Ollama(LLaVA)에게 분석을 요청합니다.
        """
        try:
            response = ollama.chat(
                model=self.model_name,
                messages=[
                    {
                        'role': 'user',
                        'content': prompt,
                        'images': [image_bytes]
                    }
                ]
            )
            return response['message']['content']
        except Exception as e:
            return f"AI 분석 실패: {str(e)}"

    def analyze_with_context(self, image_bytes, context_text):
        """
        [RAG용] 복호화된 보안 문서(Context)를 참고하여 이미지를 분석합니다.
        """
        rag_prompt = f"""
        You are a secure industrial AI assistant.
        Analyze the provided image based strictly on the following secure context document.
        
        [SECURE CONTEXT START]
        {context_text}
        [SECURE CONTEXT END]

        Question: What is this object based on the context above?
        """
        return self.analyze_image(image_bytes, rag_prompt)