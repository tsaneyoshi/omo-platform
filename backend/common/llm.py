# -*- coding: utf-8 -*-
"""
OMO Platform - LLM操作モジュール

Gemini APIの初期化と基本操作を提供
"""

import time
import random
from typing import Optional, Dict, Any
import google.generativeai as genai
from google.generativeai.types import GenerationConfig, HarmCategory, HarmBlockThreshold

from .config import get_config


# デフォルトのセーフティ設定
DEFAULT_SAFETY_SETTINGS = {
    HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
    HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_ONLY_HIGH,
}


class LLMClient:
    """Gemini APIクライアントラッパー"""
    
    def __init__(self, config=None, model_name: Optional[str] = None):
        """
        Args:
            config: Configインスタンス (Noneの場合は自動取得)
            model_name: モデル名 (Noneの場合は設定から取得)
        """
        self.config = config or get_config()
        self.model_name = model_name or self.config.gemini_model_name
        self.model = self._init_gemini()
    
    def _init_gemini(self) -> genai.GenerativeModel:
        """Gemini APIを初期化"""
        try:
            api_key = self.config.google_api_key
            genai.configure(api_key=api_key)
            
            model = genai.GenerativeModel(self.model_name)
            print(f"✨ Gemini 初期化 OK（{self.model_name}）")
            
            return model
            
        except Exception as e:
            raise RuntimeError(f"Gemini 初期化に失敗: {e}")
    
    # ========================================
    # 基本生成
    # ========================================
    
    def generate(
        self,
        prompt: str,
        generation_config: Optional[GenerationConfig] = None,
        safety_settings: Optional[Dict] = None,
        retry: int = 3,
        retry_base_delay: float = 1.0
    ):
        """
        コンテンツを生成
        
        Args:
            prompt: プロンプト
            generation_config: 生成設定
            safety_settings: セーフティ設定
            retry: リトライ回数
            retry_base_delay: リトライ基本遅延(秒)
        
        Returns:
            GenerateContentResponse
        """
        if safety_settings is None:
            safety_settings = DEFAULT_SAFETY_SETTINGS
        
        last_exc: Optional[Exception] = None
        
        for i in range(retry):
            try:
                response = self.model.generate_content(
                    prompt,
                    generation_config=generation_config,
                    safety_settings=safety_settings,
                )
                return response
                
            except Exception as e:
                last_exc = e
                print(f"⚠️ generate_content 失敗 ({i+1}/{retry}): {e}")
                
                if i == retry - 1:
                    raise
                
                # エクスポネンシャルバックオフ
                delay = retry_base_delay * (2 ** i) + random.random() * 0.3
                time.sleep(delay)
        
        raise last_exc or RuntimeError("Unknown error in generate")
    
    # ========================================
    # テキスト抽出ヘルパー
    # ========================================
    
    @staticmethod
    def extract_text(response) -> str:
        """
        レスポンスからテキストを安全に抽出
        
        Args:
            response: GenerateContentResponse
        
        Returns:
            抽出されたテキスト
        """
        try:
            # まず response.text を試す
            text = getattr(response, "text", None)
            if text:
                return text.strip()
        except Exception:
            pass
        
        # candidates.parts から抽出
        try:
            if hasattr(response, "candidates") and response.candidates:
                parts = response.candidates[0].content.parts
                text = "".join(
                    getattr(p, "text", "") 
                    for p in parts 
                    if hasattr(p, "text")
                )
                return text.strip()
        except Exception:
            pass
        
        return ""
    
    @staticmethod
    def get_finish_reason(response) -> str:
        """finish_reasonを取得"""
        try:
            if hasattr(response, "candidates") and response.candidates:
                fr = getattr(response.candidates[0], "finish_reason", None)
                return str(fr) if fr is not None else ""
        except Exception:
            pass
        return ""
    
    @staticmethod
    def get_block_reason(response) -> str:
        """block_reasonを取得"""
        try:
            pf = getattr(response, "prompt_feedback", None)
            if pf:
                br = getattr(pf, "block_reason", None)
                return str(br) if br else ""
        except Exception:
            pass
        return ""
    
    # ========================================
    # プリセット生成設定
    # ========================================
    
    @staticmethod
    def get_text_config(max_tokens: int = 16) -> GenerationConfig:
        """短いテキスト生成用の設定"""
        return GenerationConfig(
            temperature=0.0,
            max_output_tokens=max_tokens
        )
    
    @staticmethod
    def get_json_config(max_tokens: int = 10240) -> GenerationConfig:
        """JSON生成用の設定"""
        return GenerationConfig(
            temperature=0.2,
            top_p=0.9,
            top_k=40,
            max_output_tokens=max_tokens
        )
    
    @staticmethod
    def get_creative_config(max_tokens: int = 8192) -> GenerationConfig:
        """クリエイティブな生成用の設定"""
        return GenerationConfig(
            temperature=0.7,
            top_p=0.95,
            top_k=40,
            max_output_tokens=max_tokens
        )


# グローバルインスタンス
_llm_client: Optional[LLMClient] = None


def get_llm_client(config=None, model_name: Optional[str] = None) -> LLMClient:
    """
    LLMクライアントを取得
    
    Args:
        config: Configインスタンス
        model_name: モデル名
    
    Returns:
        LLMClient インスタンス
    """
    global _llm_client
    
    if _llm_client is None:
        _llm_client = LLMClient(config, model_name)
    
    return _llm_client


def reload_llm_client(config=None, model_name: Optional[str] = None) -> LLMClient:
    """LLMクライアントを再初期化"""
    global _llm_client
    _llm_client = LLMClient(config, model_name)
    return _llm_client


def create_llm_client(model_name: str, config=None) -> LLMClient:
    """
    新しいLLMクライアントを作成 (グローバルインスタンスとは別)
    
    Args:
        model_name: モデル名
        config: Configインスタンス
    
    Returns:
        新しいLLMClient インスタンス
    """
    return LLMClient(config, model_name)
