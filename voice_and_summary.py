import threading
import pyaudio
import dashscope
from dashscope.audio.asr import Recognition, RecognitionCallback, RecognitionResult
import openai
import tkinter as tk
from tkinter import messagebox

# 初始化API密钥
def get_key(filename):
    with open(filename, 'r') as file:
        lines = file.readlines()
        dashscope_key = lines[0].strip()
        openai_key = lines[1].strip()
    return dashscope_key, openai_key

dashscope.api_key, openai.api_key = get_key('key.txt')

openai.api_base = "https://api.chatfire.cn/v1"

# 全局变量
text_buffer = ""
state = "stopped"
recognition_condition = threading.Condition()
is_recognition_active = False

# 自定义回调
class Callback(RecognitionCallback):
    def on_event(self, result: RecognitionResult) -> None:
        global text_buffer
        sentence = result.get_sentence()
        if isinstance(sentence, dict):
            sentence_text = sentence.get('text', '')
        else:
            sentence_text = sentence

        if state != "paused":
            text_buffer += " " + sentence_text
            update_text_display(sentence_text)  # 更新实时显示

# 更新实时文字显示
def update_text_display(sentence_text):
    text_display.config(state=tk.NORMAL)
    text_display.insert(tk.END, sentence_text + '\n')
    text_display.see(tk.END)
    text_display.config(state=tk.DISABLED)

# 语音识别线程
def start_recognition():
    global is_recognition_active, state
    mic = pyaudio.PyAudio()
    stream = mic.open(format=pyaudio.paInt16, channels=1, rate=16000, input=True)
    recognition = Recognition(model='paraformer-realtime-v2', format='pcm', sample_rate=16000, callback=Callback())
    recognition.start()
    is_recognition_active = True

    try:
        while state != "stopped":
            with recognition_condition:
                if state == "paused":
                    recognition_condition.wait()
            if state == "running":
                data = stream.read(3200, exception_on_overflow=False)
                recognition.send_audio_frame(data)

    finally:
        if is_recognition_active:
            recognition.stop()
            is_recognition_active = False
            stream.stop_stream()
            stream.close()
            mic.terminate()

# 文本摘要
def summarize_text():
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an assistant that creates an overall summary of the collected text.Answer in Chinese."},
            {"role": "user", "content": text_buffer.strip()}
        ]
    )
    return response['choices'][0]['message']['content']

# 弹窗显示总结
def show_summary():
    summary = summarize_text()
    messagebox.showinfo("Summary", summary)

# 润色发言
def refine_speech(text):
    response = openai.ChatCompletion.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are an assistant that refines speech content by removing unnecessary pauses, correcting unclear or inappropriate expressions, and making the language clear and appropriate."},
            {"role": "user", "content": text}
        ]
    )
    return response['choices'][0]['message']['content']

# 保存文本到文件
def save_text_to_file(text, filename):
    with open(filename, 'w', encoding='utf-8') as file:
        file.write(text)

# 按钮处理函数
def start_button():
    global state
    if state == "paused":
        with recognition_condition:
            state = "running"
            recognition_condition.notify()
    elif not is_recognition_active:
        state = "running"
        threading.Thread(target=start_recognition).start()

def pause_button():
    global state
    if state == "running":
        state = "paused"

def stop_button():
    global state
    state = "stopped"
    with recognition_condition:
        recognition_condition.notify()
    if is_recognition_active:
        threading.Thread(target=save_and_refine_text).start()

# 保存和润色文本
def save_and_refine_text():
    summary = summarize_text()
    messagebox.showinfo("Summary", summary)
    save_text_to_file(summary, 'collected_text.txt')
    refined_text = refine_speech(text_buffer)
    save_text_to_file(refined_text, 'refined_speech.txt')
    messagebox.showinfo("Finished!", "Refined text and summary have been saved.")

# 创建主窗口
root = tk.Tk()
root.title("Speech Recognition App")

# 创建按钮
start_btn = tk.Button(root, text="Start", command=start_button)
pause_btn = tk.Button(root, text="Pause", command=pause_button)
stop_btn = tk.Button(root, text="Stop", command=stop_button)
summarize_btn = tk.Button(root, text="Summarize", command=show_summary)

# 布局按钮
start_btn.grid(row=0, column=0, padx=10, pady=10)
pause_btn.grid(row=0, column=1, padx=10, pady=10)
stop_btn.grid(row=0, column=2, padx=10, pady=10)
summarize_btn.grid(row=0, column=3, padx=10, pady=10)

# 创建文本显示框
text_display = tk.Text(root, wrap=tk.WORD, height=20, width=60, state=tk.DISABLED)
text_display.grid(row=1, column=0, columnspan=4, padx=10, pady=10)

# 启动主循环
root.mainloop()
