#!/bin/bash

# 设置OpenAI API密钥（使用您在Chrome扩展中设置的相同值）
export OPENAI_API_KEY="33b305a9-ceae-4732-9c2e-2df6b945a46b"

# 使用doubao-1.5-ui-tars-250328模型（与您的截图一致）
export OPENAI_BASE_URL="https://ark.cn-beijing.volces.com/api/v3"
export MIDSCENE_MODEL_NAME="doubao-1.5-ui-tars-250328"
export MIDSCENE_USE_VLM_UI_TARS="DOUBAO"

echo "环境变量已设置:"
echo "OPENAI_API_KEY: [已设置]"
echo "OPENAI_BASE_URL: $OPENAI_BASE_URL"
echo "MIDSCENE_MODEL_NAME: $MIDSCENE_MODEL_NAME"
echo "MIDSCENE_USE_VLM_UI_TARS: $MIDSCENE_USE_VLM_UI_TARS"

echo -e "\n请确保在Chrome扩展中点击了'Allow connection'按钮，然后按回车继续..." 