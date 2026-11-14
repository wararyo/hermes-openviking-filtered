# openviking_filtered

[OpenViking](https://github.com/volcengine/OpenViking/tree/main/examples/hermes-plugin) の Hermes 記憶プロバイダを包み、**プラグインが会話に差し込んだターンを、ユーザーの発言として記憶させない**ための記憶プロバイダです。

## なぜ必要か

[heartbeat2](https://github.com/electricsheephq/heartbeat2) などのプラグインが `ctx.inject_message` で起こしたターンは、Hermes から記憶プロバイダへ「ユーザー本人の発言」として渡されます（[NousResearch/hermes-agent#130622](https://github.com/NousResearch/hermes-agent/issues/130622)）。そのため OpenViking が、wake の指示文（`⟦pulse o:… ⟧ [HeartBeat 2.0 · wake …] Your note: …`）から「ユーザーについての事実」を抽出してしまいます。

## 何をするか

OpenViking の `sync_turn` に渡る前に、差し込まれたターンの**ユーザー側だけ**を短いラベルに差し替えます。

```
[自動ターン: HeartBeat 2.0 の予約によりエージェント自身が起動した。この行はユーザーの発言ではない]
```

- アシスタントの返事とツールの実行結果はそのまま記憶されます。wake 中にメールを確認して分かったことなどは残ります。
- 対象になるターン：
  - 1行目付近に heartbeat2 の目印 `⟦pulse o:<id> a:<n>⟧`（グループでは ` n:<16桁hex>` 付き）があるターン
  - `turn_author` が `{"id": "plugin:<id>", "is_bot": true}` のターン。#130622 の修正が Hermes に入った後に効きます
- それ以外（人間の発言、他の Bot の発言 `bot:<profile>`）は一切変更しません。
- 記憶の呼び出し（recall）やツールなど、`sync_turn` 以外の動作は OpenViking そのままです。

## 前提

- Hermes Agent と、カタログ版の OpenViking プラグイン（`hermes plugins install openviking`）がインストール済みで、設定済みであること
- `plugins.isolation` が既定の `in_process` であること（`host` では未検証）

## インストール（gateway を動かしているマシンで）

ディレクトリ名は `openviking_filtered` にする必要があります。

```bash
# GitHub に置いた場合
hermes plugins install <GitHubユーザー名>/hermes-openviking-filtered

# または直接 clone する場合
git clone <このリポジトリのURL> "${HERMES_HOME:-$HOME/.hermes}/plugins/openviking_filtered"
```

記憶プロバイダを切り替えて、gateway を再起動します。

```bash
hermes config set memory.provider openviking_filtered
hermes gateway restart
```

OpenViking の設定（`memory.openviking` セクション、`OPENVIKING_*` 環境変数、`~/.openviking/ovcli.conf`）はそのまま使われます。

## 元に戻す

```bash
hermes config set memory.provider openviking
hermes gateway restart
```

## 注意点

- **`hermes openviking local …` が使えなくなります。** Hermes は、有効な記憶プロバイダの CLI しか登録しないためです。Quick Local のサーバーを操作するときは、一時的に `memory.provider` を `openviking` に戻してください。
- Quick Local（ローカル組み込みサーバー）の構成では、OpenViking の一部の処理が `memory.provider == "openviking"` を前提にしています。CLI の `start` / `restart` がそうなっていることは確認済みです。自前のサーバーやクラウドに接続している場合は関係ありません。
- プロバイダの `name` は `openviking` のままです。ログや `hermes memory status` には `openviking` と表示されます。
- heartbeat2 の目印の形式は、heartbeat2 0.3.14 時点のものです。形式が変わったら、`filtering.py` の `HEARTBEAT2_MARKER` を更新してください。
- OpenViking 側は `turn_author["id"]` で発言者（peer）を決めています。#130622 の修正が入ると、差し込まれたターンは `plugin:<id>` という別の peer として送られます。

## 動作確認

OpenViking のトレースログを有効にして gateway を起動すると、送信される `user_preview` を確認できます。wake のターンでラベルになっていれば正しく動いています。

```bash
HERMES_OPENVIKING_SYNC_TRACE=1 hermes gateway run   # 確認用。普段は不要
```

## 不要になる条件

次の両方が入ったら、このプラグインは不要です。`memory.provider` を `openviking` に戻してください。

1. Hermes：差し込まれたターンに `is_bot` の `turn_author` が付く（#130622）
2. OpenViking：`turn_author.is_bot` のターンを記憶しない、または区別して扱う

## テスト

Hermes がなくても動きます。

```bash
uvx pytest tests      # または: python -m pytest tests
```
