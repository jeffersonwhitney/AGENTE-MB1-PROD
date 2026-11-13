import os
import json
from typing import Any
from dotenv import load_dotenv
from openai import OpenAI
from tenacity import retry, wait_exponential, stop_after_attempt

load_dotenv()

# Cliente configurado com timeout rígido de 10 segundos
client = OpenAI(
    api_key=os.getenv("DEEPSEEK_API_KEY"),
    base_url="https://api.deepseek.com",
    timeout=10.0
)

# ==========================================
# 1. DEFINIÇÃO DAS DUAS FERRAMENTAS (Read & Write)
# ==========================================
tools: list[Any] = [
    {
        "type": "function",
        "function": {
            "name": "consultar_status_pedido",
            "description": "Consulta o status atual e detalhes de um pedido no ERP corporativo.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_pedido": {"type": "string", "description": "O ID alfanumérico do pedido (ex: PED-9988)."}
                },
                "required": ["id_pedido"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "atualizar_status_entrega",
            "description": "AÇÃO REAL: Altera o status de entrega de um pedido no banco de dados de logística.",
            "parameters": {
                "type": "object",
                "properties": {
                    "id_pedido": {"type": "string", "description": "O ID do pedido a ser atualizado."},
                    "novo_status": {"type": "string", "description": "O novo status (ex: 'SEPARADO', 'EM_ROTA', 'ENTREGUE')."}
                },
                "required": ["id_pedido", "novo_status"]
            }
        }
    }
]

# Funções locais simulando sistemas reais
def consultar_status_pedido(id_pedido: str) -> str:
    print(f"\n[SISTEMA LOCAL] Lendo banco de dados para o pedido: {id_pedido}...")
    db = {"PED-9988": {"cliente": "Varejo Express", "status": "PENDENTE", "rota": "João Pessoa - PB"}}
    return json.dumps(db.get(id_pedido, {"erro": "Pedido não encontrado."}))

def atualizar_status_entrega(id_pedido: str, novo_status: str) -> str:
    print(f"\n[AÇÃO REAL - ESCRITA] Alterando banco de dados: Pedido {id_pedido} -> Novo Status: {novo_status}")
    # Simula a alteração de estado no sistema externo
    return json.dumps({"sucesso": True, "id_pedido": id_pedido, "status_atualizado": novo_status})

# ==========================================
# 2. RESILIÊNCIA DE REDE COM TENACITY
# ==========================================
@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    reraise=True
)
def chamar_llm(mensagens: list[Any]):
    return client.chat.completions.create(
        model="deepseek-chat", # ou deepseek-v4-flash dependendo do seu modelo ativo
        messages=mensagens,
        tools=tools,
        tool_choice="auto"
    )

# ==========================================
# 3. EXECUÇÃO DO FLUXO E MÉTRICA DE CUSTO
# ==========================================
def executar_agente():
    # 1. Carrega as instruções do sistema
    with open("AGENTS.md", "r", encoding="utf-8") as f:
        system_instructions = f.read()

    # O contexto começa apenas com a instrução do sistema
    messages: list[Any] = [
        {"role": "system", "content": system_instructions}
    ]

    print("=== 🤖 AGENTE LOGÍSTICO INICIADO ===")
    print("Digite 'sair' para encerrar a sessão e ver os custos.\n")
    
    tokens_input_total = 0
    tokens_output_total = 0

    # 2. Laço infinito para o chat com o usuário
    while True:
        pergunta_usuario = input("\n[Você]: ")
        
        if pergunta_usuario.strip().lower() == "sair":
            break
            
        messages.append({"role": "user", "content": pergunta_usuario})

        try:
            # 3. Laço interno para a IA rodar ferramentas em cadeia (até 5 por turno)
            for i in range(5):
                response = chamar_llm(messages)
                response_message = response.choices[0].message
                messages.append(response_message.model_dump(exclude_none=True))

                if response.usage:
                    tokens_input_total += response.usage.prompt_tokens
                    tokens_output_total += response.usage.completion_tokens

                if response_message.tool_calls:
                    for tool_call in response_message.tool_calls:
                        func = getattr(tool_call, "function", None)
                        if not func:
                            continue

                        function_name = func.name
                        function_args = json.loads(func.arguments or "{}")

                        print(f"\n⚙️ [IA DECIDIU EXECUTAR A FERRAMENTA]: {function_name}")
                        print(f"📦 Argumentos: {function_args}")

                        function_response = ""
                        if function_name == "consultar_status_pedido":
                            function_response = consultar_status_pedido(id_pedido=str(function_args.get("id_pedido", "")))
                        elif function_name == "atualizar_status_entrega":
                            function_response = atualizar_status_entrega(
                                id_pedido=str(function_args.get("id_pedido", "")),
                                novo_status=str(function_args.get("novo_status", ""))
                            )

                        # Devolve o resultado da ferramenta para o histórico
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": function_response,
                        })
                else:
                    # Se não tem tool_call, a IA parou para falar com você
                    print(f"\n[AGENTE]: {response_message.content}")
                    break # Quebra o laço interno de tools e volta a esperar o seu input

        except Exception as e:
            print(f"\n[FALHA CRÍTICA] Erro na execução: {e}")

    # Quando você digitar 'sair', ele compila o custo da sessão toda
    custo_estimado = (tokens_input_total * 0.00000014) + (tokens_output_total * 0.00000028)
    print("\n========================================")
    print(f"📊 [MÉTRICA DE CUSTO DA SESSÃO]")
    print(f"- Tokens de Input Totais: {tokens_input_total}")
    print(f"- Tokens de Output Totais: {tokens_output_total}")
    print(f"- Custo Estimado Total: ${custo_estimado:.6f} USD")
    print("========================================")

if __name__ == "__main__":
    executar_agente()

if __name__ == "__main__":
    # Testando um fluxo que exige leitura e depois uma AÇÃO REAL de escrita
    pergunta = "Verifique o status do pedido PED-9988 e, caso ele exista, atualize o status de entrega dele para 'EM_ROTA'."
    executar_agente(pergunta)