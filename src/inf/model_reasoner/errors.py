from src.app.ports.model_reasoner import ModelUnavailableError


def wrong_model_name(provider: str, model: str) -> ModelUnavailableError:
    return ModelUnavailableError(
        f"Model '{model}' không tồn tại hoặc không dùng được ở {provider}. "
        "Hãy chọn model khác hoặc báo admin kiểm tra lại tên chuẩn của model."
    )


def wrong_reasoning_mode(model: str, mode) -> ModelUnavailableError:
    return ModelUnavailableError(
        f"Model '{model}' không hỗ trợ chế độ suy luận '{mode}'. "
        "Hãy chọn chế độ khác hoặc báo admin kiểm tra lại các chế độ suy luận của model."
    )


def missing_api_key(provider: str) -> ModelUnavailableError:
    return ModelUnavailableError(
        f"Chưa cấu hình đúng API key của {provider}. Báo admin kiểm tra lại."
    )


def tools_not_supported(provider: str, model: str) -> ModelUnavailableError:
    return ModelUnavailableError(
        f"Model '{model}' ở {provider} không hỗ trợ gọi tool, agent không dùng được model này. "
        "Hãy chọn model khác hoặc báo admin."
    )


def translate_api_error(e: Exception, provider: str, model: str, mode) -> Exception:
    '''
    Đổi lỗi của SDK kiểu OpenAI (openai, groq cùng dạng APIStatusError) thành ModelUnavailableError
    khi lỗi do cấu hình model sai. Lỗi khác (mạng, quá tải...) trả lại nguyên để bên gọi raise tiếp.
    '''
    status = getattr(e, "status_code", None)
    param = (getattr(e, "param", None) or "").lower()
    message = str(getattr(e, "message", e)).lower()

    if status == 401:
        return missing_api_key(provider)

    if status == 404 or (status == 400 and (param == "model" or "model_not_found" in message or "does not exist" in message)):
        return wrong_model_name(provider, model)

    # "thinking": model Claude không hỗ trợ adaptive thinking / effort
    if status == 400 and ("reasoning" in param or "reasoning" in message or "effort" in message or "thinking" in message):
        return wrong_reasoning_mode(model, mode)

    if status == 400 and ("tool" in param or "does not support tools" in message or "tool use is not supported" in message):
        return tools_not_supported(provider, model)

    return e
