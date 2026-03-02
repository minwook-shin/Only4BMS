# Only4BMS

<img width="2556" height="1439" alt="스크린샷 2026-02-24 230333" src="https://github.com/user-attachments/assets/68d1891b-891b-4927-ab81-96f7bbc098f7" />

[![Only4BMS AI Battle1](https://img.youtube.com/vi/mrSUp4h7DnE/0.jpg)](https://youtu.be/mrSUp4h7DnE)

7 teclas? Não, obrigado.

Este é um driver BMS baseado em Pygame que **reorganiza forçosamente** todos os gráficos BMS em **4 teclas (DFJK)** para reprodução.

## Visão Geral do Projeto

O Only4BMS foi criado para puristas de 4 teclas que encaram gráficos BMS complexos como os de 7 teclas ou 14 teclas e pensam: "Como eu deveria tocar tudo isso?"

Este projeto usa Pygame para analisar arquivos BMS e fornece um ambiente onde você pode desfrutar de qualquer formato de gráfico **remapeado em 4 pistas** juntamente com sons de teclas.

## Principais Recursos

**Mapeamento Forçado de 4 Teclas**: Atribui automaticamente gráficos de 5 teclas, 7 teclas, 10 teclas e 14 teclas a 4 pistas (D, F, J, K) usando algoritmos matemáticos.

**Verificador de Densidade**: Verifica e visualiza a densidade das notas quando os gráficos de 7 teclas são consolidados em 4 teclas.

## 🛠️ Tecnologias Utilizadas

**Linguagem**: Python 3.x

**Biblioteca**: Pygame (Som e Renderização)

**Formato**: Be-Music Script (.bms, .bme, .bml)

## Como Jogar (Adicionando Músicas e Executando)

1. **Obtenha o Jogo**: Baixe o `Only4BMS.exe` pré-compilado ou compile você mesmo.
2. **Lançamento**: Basta executar o `Only4BMS.exe` de qualquer pasta. 
3. **A Pasta `bms`**: Ao iniciar, o jogo cria automaticamente uma pasta `bms` no mesmo diretório do executável. Se nenhuma música for encontrada, ele gera uma música demo básica.
4. **Adicionando Suas Próprias Músicas**: 
   - Baixe arquivos BMS/BME/BML e suas mídias associadas (áudio/vídeos BGA).
   - Extraia-os em suas próprias subpastas dentro do diretório `bms/`.
   - Exemplo de estrutura:
     ```text
     [Diretório contendo Only4BMS.exe]
     ├── Only4BMS.exe
     └── bms/
         ├── Awesome Track/
         │   ├── song.bms
         │   ├── audio.wav
         │   └── video.mp4
         └── Another Track/
             └── ...
     ```

## 🎵 Modo Curso (Treinamento Roguelike)

Cansado das mesmas músicas? Entre no **Modo Curso**, um modo de treinamento processual e infinito!
- Gráficos gerados proceduralmente que são diferentes a cada vez.
- Dificuldades progressivas: Iniciante (BPM 80~110), Intermediário (BPM 120~160), Avançado (BPM 160~200).
- Encontre notas longas e truques de BPM (mudanças de velocidade) conforme avança.
- Cada estágio dura cerca de 30 segundos. Sobreviva e veja o que vem a seguir!

## 🤖 Treinamento de IA e Multiplayer

O Only4BMS apresenta um modo Multiplayer de IA alimentado por **Aprendizagem por Reforço (PPO)**.

### Como Funciona
- A IA é treinada usando `stable-baselines3` em faixas de ritmo geradas proceduralmente e músicas demo livres de direitos.
- **Conformidade Legal**: Para garantir padrões éticos, os lançamentos oficiais incluem modelos treinados *exclusivamente* em dados não comerciais durante o processo de CI/CD.
- **Dificuldades**:
  - **NORMAL**: Treinado por 25.000 passos. Alta precisão, mas com erros ocasionais semelhantes aos humanos.
  - **HARD**: Treinado por 40.000 passos. Sincronização e manutenção de combo quase perfeitas.

### Treinamento Local
Se você deseja treinar seus próprios modelos localmente:
1. Instale as dependências: `pip install stable-baselines3 shimmy gymnasium torch`
2. Execute o script de treinamento: `python -m only4bms.ai.train`
3. Os arquivos `model_normal.zip` e `model_hard.zip` gerados serão salvos em `src/only4bms/ai/`.

### CI/CD Automatizado
Nosso fluxo de trabalho do GitHub Actions treina automaticamente os modelos de IA do zero usando a música `Mock Song Demo` para cada lançamento. Isso garante que o binário distribuído aos usuários esteja sempre "limpo" e otimizado.

<a href="https://minwook-shin.itch.io/only4bms" class="btn">Jogar no itch.io</a>

## Declaração de Transparência:

O Only4BMS é um projeto solo apaixonado.

Para agilizar o processo de produção, incorporei tecnologia assistida por IA para o código.

Isso me permitiu expandir os limites do que uma única pessoa pode criar, garantindo que o jogo final pareça polido e completo.

## 🤝 Contribuindo

Relatos de bugs e sugestões de recursos de usuários de 4 teclas são sempre bem-vindos!

## 📜 Licença

Licença MIT - Sinta-se à vontade para modificar e distribuir. Apenas, por favor, mantenha a paz para os usuários de 4 teclas.
