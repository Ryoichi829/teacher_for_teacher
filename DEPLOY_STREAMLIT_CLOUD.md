# Streamlit Community Cloud デプロイ手順

## 1. GitHubへ置くファイル

```text
teacher-for-teachers/
├─ app.py
├─ teacher_agent.py
├─ requirements.txt
├─ .gitignore
└─ knowledge/
   ├─ lesson_plan.json
   ├─ slide_guides.json
   └─ web_apps/
      ├─ tokenization.json
      └─ word2vec.json
```

教材JSONにはAPIキーを入れず、この構成のままGitHubへ登録します。

## 2. GitHubリポジトリを作成する

1. GitHubで新しいリポジトリを作成します。
2. 上記のファイルとフォルダを、階層を変えずに登録します。
3. `.env`、`.streamlit/secrets.toml`、`conversation_history.db`は登録しません。

## 3. Streamlit Community Cloudでアプリを作成する

1. `https://share.streamlit.io/` にGitHubアカウントでサインインします。
2. `Create app` を選びます。
3. GitHubのリポジトリ、ブランチ、起動ファイルを指定します。
4. 起動ファイルは `app.py` です。
5. `Advanced settings` を開き、Python 3.12を選びます。
6. Secrets欄へ次を入力します。

```toml
OPENAI_API_KEY = "ここにOpenAI APIキー"
```

7. `Deploy` を選びます。

## 4. 動作確認

次の質問を順番に試します。

```text
分かち書きのアプリの使い方をしりたい
Word2Vecの単語のアナロジーは、どう進めればよいですか？
スライド25では、どのように話せばよいですか？
```

## 5. データの扱い

- `lesson_plan.json`、`slide_guides.json`、Webアプリガイドは読み取り用教材なので、GitHubへ登録します。
- OpenAI APIキーはSecretsだけに登録し、GitHubへ置きません。
- `conversation_history.db`はGitHubへ置きません。
- Community Cloud上のSQLiteは、再起動や再デプロイ後の恒久保存先としては使用しません。
- 研究用に会話ログを確実に保存する場合は、外部データベースへ変更します。

## 6. 第三者へ公開する前の注意

- OpenAI APIの利用料金は、Secretsに登録したAPIキーの所有者へ発生します。
- OpenAI側で利用上限と請求アラートを設定します。
- 生徒・教員には、氏名、学校名、個人情報、秘密情報を入力しないよう表示します。
- 研究データとして会話を保存する場合は、利用目的、保存項目、保存期間を説明して同意を得ます。
