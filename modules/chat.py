# modules/chat.py
import streamlit as st
import streamlit.components.v1 as components
import pandas as pd
import json
from modules.utils import detectar_tipo_pergunta, executar_analise_segura, gerar_contexto_dados
from modules.tutorial_helper import tutorial_button # <-- NOVO IMPORT


def _is_resumo(texto):
    if not texto:
        return False
    return str(texto).lstrip().startswith("Resumo Geral")


def _render_copy_button(texto, key):
    btn_id = f"copy_btn_{key}"
    safe_text = json.dumps(texto)
    html = f"""
    <div style="margin-top:6px;">
      <button id="{btn_id}" style="padding:6px 10px;border-radius:6px;border:1px solid #d0d0d0;background:#f7f7f7;cursor:pointer;">
        Copiar resumo
      </button>
      <span id="{btn_id}_status" style="margin-left:8px;font-size:12px;color:#6c757d;"></span>
    </div>
    <script>
      const btn = document.getElementById("{btn_id}");
      const status = document.getElementById("{btn_id}_status");
      if (btn) {{
        btn.addEventListener("click", async () => {{
          try {{
            await navigator.clipboard.writeText({safe_text});
            status.textContent = "Copiado!";
            setTimeout(() => status.textContent = "", 2000);
          }} catch (e) {{
            status.textContent = "Falha ao copiar";
          }}
        }});
      }}
    </script>
    """
    components.html(html, height=48)


def _render_chat_message(message, idx):
    content = message.get("content", "")
    st.markdown(content)
    if message.get("role") == "assistant" and _is_resumo(content):
        _render_copy_button(content, idx)

def chat_interface():
    # 🚨 NOVO: Chamada para o botão de tutorial (Substitui o st.subheader original)
    tutorial_button("Chat/IA", "💬 Co-piloto Mercúrio")
    
    chat_container = st.container(height=600)
    
    # Redesenha o histórico a partir do session_state
    with chat_container:
        for idx, message in enumerate(st.session_state.display_history):
            with st.chat_message(message["role"]):
                _render_chat_message(message, f"history_{idx}")

    if prompt := st.chat_input("Envie uma pergunta ou mensagem..."):
        # Adiciona a mensagem do usuário ao histórico
        st.session_state.display_history.append({"role": "user", "content": prompt})
        st.session_state.chat_history.append({"role": "user", "content": prompt})
        
        # Redesenha a mensagem do usuário IMEDIATAMENTE no container
        with chat_container:
            with st.chat_message("user"):
                _render_chat_message({"role": "user", "content": prompt}, "current_user")

        # --- NOVA LÓGICA DE SPINNER ---
        # Agora, a resposta do assistente é gerada dentro de um spinner
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Mercúrio está analisando..."): # [cite]
                    prompt_lower = prompt.lower()
                    palavras_chave_criador = [
                        "criou", "desenvolveu", "fez", "fabricou", "produziu", "concebeu",
                        "pessoa mais", "bonita", "linda", "foda", "maravilhosa", "inteligente", "criador"
                    ]
                    
                    prompt_lower = prompt.lower()
                    tipo = detectar_tipo_pergunta(prompt_lower)
                    resposta_final = "" # Inicializa a resposta
                    
                    # Tenta primeiro o agente especialista se a pergunta for específica
                    if tipo != "geral":
                        try:
                            resultado_analise, erro = st.session_state.executar_analise_pandas_fn("", prompt, tipo)
                            
                            # Se o agente retornar um erro controlado (como pergunta inválida), não faz nada, deixando a lógica de fallback agir
                            if erro:
                                pass 
                            else:
                                resposta_final = str(resultado_analise)
                        except Exception as e:
                            # Se qualquer outro erro ocorrer, registra e deixa o fallback agir
                            log_timestamp = pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')
                            st.session_state.app_log.append(f"[{log_timestamp}] INFO: Agente especialista falhou ({e}), usando fallback para o modelo geral.")
                            pass
                    
                    # Se o agente especialista não produziu uma resposta, usa o modelo geral com contexto
                    if not resposta_final:
                        data_context = gerar_contexto_dados()
                        system_prompt = f"""
Você é Mercúrio, um assistente virtual brasileiro especialista em análise de dados e logística.
Sua personalidade é amigável, prestativa e direta.

A seguir, um resumo dos dados que estão carregados na aplicação. Use este contexto para basear sua resposta, se a pergunta for sobre eles.
---
CONTEXTO DOS DADOS:
{data_context}
---

TAREFA:
Responda à pergunta do usuário.
- Se a pergunta for sobre os dados, use o contexto acima para responder.
- Se a pergunta for geral (não relacionada aos dados), responda como um assistente geral prestativo.
- Mantenha sempre a personalidade de Mercúrio. Nunca diga que você é um modelo de linguagem ou IA.
"""
                        full_prompt = system_prompt + "\n\nPergunta do usuário: " + prompt
                        try:
                            response = st.session_state.model.generate_content(full_prompt)
                            resposta_final = response.text.strip()
                        except Exception as e:
                            resposta_final = f"Ocorreu um erro ao contatar a IA. Detalhes: {e}"
                
                # O spinner é substituído pela resposta final
                _render_chat_message({"role": "assistant", "content": resposta_final}, "current_assistant")
        # --- FIM DA LÓGICA DE SPINNER ---

        # Adiciona a resposta final do assistente ao histórico
        st.session_state.display_history.append({"role": "assistant", "content": resposta_final})
        
        # st.rerun() # Removido para permitir que o spinner funcione corretamente
