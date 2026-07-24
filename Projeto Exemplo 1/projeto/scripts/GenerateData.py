import tkinter as tk
from tkinter import messagebox, ttk
import oracledb
import random
import yaml
import os
import hashlib
import traceback
from datetime import datetime, timedelta, date

# ============================================================================
# VendasODS — Gerador de dados de teste (Oracle)
#
# Convertido de MySQL (pymysql) para Oracle usando o driver oficial
# python-oracledb em modo THIN (puro Python, NAO exige Oracle Instant
# Client instalado). Aponta para o mesmo schema "vendasods" usado como
# fonte de extracao pelos scripts ext001/ext002/ext003 (ver
# implantacao/base-dados/).
#
# Uso principal: gerar trafego real de INSERT/UPDATE/DELETE na fonte
# Oracle para validar a extracao incremental por janela de dias dos
# scripts ext002 (Pedidos/PedItem) e ext003 (Devolucoes/Devolucao_Item) -
# ou seja, confirmar que uma mudanca recente na fonte e de fato capturada
# na proxima execucao do pipeline, nao so a carga inicial (INITIAL).
#
# Dependencias: pip install oracledb pyyaml  (ver requirements.txt)
#
# Nota sobre identificadores: as tabelas/colunas do schema VENDASODS foram
# criadas com nomes entre aspas duplas, mistos de maiusculas/minusculas
# (ex. "Pedidos", "Data_Venda") — no Oracle isso torna o nome
# case-sensitive. Por isso toda referencia a tabela/coluna neste arquivo
# usa aspas duplas com a grafia exata do DDL (create_database_vendasods.sql).
# Aliases de coluna tambem sao citados entre aspas para preservar o nome
# exato esperado pelas chaves de dict usadas no codigo (Oracle, por padrao,
# converte alias nao citado para MAIUSCULO).
# ============================================================================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
DEFAULT_CONFIG_FILE = os.path.join(PROJECT_ROOT, "config_conexao.yaml")


def calcular_quantidade_devolucao(qtde_venda, prob_qtde, valor_aleatorio, rand_int=None):
    """Retorna a quantidade a devolver para um item com base na probabilidade de devolução completa."""
    if qtde_venda <= 0:
        return 0

    if rand_int is None:
        rand_int = random.randint

    if valor_aleatorio < prob_qtde:
        return qtde_venda

    if qtde_venda <= 1:
        return 1

    return rand_int(1, qtde_venda)


# --- Módulo de Segurança (Conforme Especificações item 5) ---
def encrypt_password(password):
    """Criptografa a senha para armazenamento seguro no YAML."""
    return hashlib.sha256(password.encode()).hexdigest()


def to_bind_date(d):
    """Converte date -> datetime (bind mais previsível para colunas DATE do Oracle)."""
    if d is None:
        return None
    if isinstance(d, datetime):
        return d
    if isinstance(d, date):
        return datetime.combine(d, datetime.min.time())
    return d


def _output_type_handler(cursor, metadata):
    """Colunas DATE do Oracle sempre voltam como datetime.datetime (o tipo DATE do
    Oracle tem componente de hora, diferente do DATE do MySQL). O código deste
    arquivo foi originalmente escrito para o pymysql, que devolve datetime.date
    para colunas DATE - por isso aqui convertemos de volta para date na leitura,
    preservando o mesmo comportamento (comparações e aritmética de data, e o
    str(valor) usado para pré-preencher campos de texto no formato AAAA-MM-DD)."""
    if metadata.type_code is oracledb.DB_TYPE_DATE:
        return cursor.var(
            metadata.type_code,
            arraysize=cursor.arraysize,
            outconverter=lambda v: v.date() if v is not None else None,
        )


def fetch_as_dict(cursor):
    """Configura o cursor para devolver linhas como dict (equivalente ao DictCursor do pymysql)."""
    if cursor.description is not None:
        columns = [col[0] for col in cursor.description]
        cursor.rowfactory = lambda *args: dict(zip(columns, args))
    return cursor


def execute(cursor, sql, params=None):
    """Executa a query e, se houver resultado (SELECT), configura fetch por dict-row."""
    try:
        cursor.execute(sql, params or {})
    except oracledb.Error as e:
        # Reraise com o SQL/params anexados - sem isso a mensagem de erro do
        # Oracle nao diz qual das varias queries executadas falhou.
        raise RuntimeError(f"{e}\nSQL: {sql}\nParams: {params or {}}") from e
    return fetch_as_dict(cursor)


class VendasODSApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Sistema VendasODS - Pedro Pinto")
        self.root.geometry("1100x750")
        self.config_file = self.resolver_config_file()
        self.db_config = self.carregar_config()
        self.setup_ui()

    def resolver_config_file(self):
        """Resolve o caminho do arquivo de configuração a partir do diretório do projeto."""
        candidates = [
            DEFAULT_CONFIG_FILE,
            os.path.join(SCRIPT_DIR, "config_conexao.yaml"),
            os.path.join(os.getcwd(), "config_conexao.yaml"),
        ]

        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return os.path.abspath(candidate)

        return os.path.abspath(DEFAULT_CONFIG_FILE)

    def carregar_config(self):
        """Carrega as configurações do arquivo YAML."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f)
            except Exception:
                return None
        return None

    def setup_ui(self):
        """Interface Principal: Menu lateral à esquerda e Log à direita (Conforme Especificações item 1)."""
        self.side_menu = ttk.Frame(self.root, padding="15")
        self.side_menu.pack(side="left", fill="y")

        ttk.Label(self.side_menu, text="MENU PRINCIPAL", font=("Helvetica", 12, "bold")).pack(pady=(0, 20))

        buttons = [
            ("1. Atualiza Dados Históricos", self.janela_confirmacao_historica),
            ("2. Gera Vendas Recentes", self.abrir_cdc),
            ("3. Atualizar Data Remessa", self.abrir_atualizar_remessa),
            ("4. Cancelar Pedidos", self.abrir_cancelar_pedidos),
            ("5. Gera Devoluções...", self.abrir_gerar_devolucoes),
            ("6. Atualiza Tabelas de Preço", self.abrir_atualiza_tabelas),
            ("7. Apagar Registros", self.abrir_apagar_registros),
            ("8. Configura Conexão", self.abrir_configuracao)
        ]

        for text, cmd in buttons:
            ttk.Button(self.side_menu, text=text, width=30, command=cmd).pack(pady=5)

        ttk.Frame(self.side_menu).pack(fill="both", expand=True)
        ttk.Button(self.side_menu, text="Sair", width=30, command=self.root.quit).pack(side="bottom", pady=10)

        self.log_frame = ttk.Frame(self.root, padding="10")
        self.log_frame.pack(side="right", fill="both", expand=True)

        ttk.Label(self.log_frame, text="Log de Execução", font=("Helvetica", 10, "bold")).pack(anchor="w")
        self.txt_log = tk.Text(self.log_frame, bg="#1e1e1e", fg="#00ff00", font=("Consolas", 10))
        self.txt_log.pack(fill="both", expand=True, pady=5)

    def log(self, msg):
        """Adiciona mensagens à área de log."""
        ts = datetime.now().strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] {msg}\n")
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    def get_db_connection(self):
        """Estabelece conexão com o banco de dados Oracle (Conforme Especificações item 5)."""
        if not self.db_config:
            messagebox.showwarning("Conexão", "Configure a conexão antes de prosseguir.")
            return None
        try:
            dsn = oracledb.makedsn(
                self.db_config.get('host'),
                int(self.db_config.get('port', 1521)),
                service_name=self.db_config.get('service_name', 'XEPDB1')
            )
            conn = oracledb.connect(
                user=self.db_config.get('user'),
                password=self.db_config.get('password_raw'),
                dsn=dsn
            )
            conn.outputtypehandler = _output_type_handler
            return conn
        except Exception as e:
            messagebox.showerror("Erro de Conexão", f"Não foi possível conectar ao banco:\n{e}")
            return None

    # --- 1. ATUALIZA DADOS HISTÓRICOS (Conforme Especificações item 2) ---
    def janela_confirmacao_historica(self):
        try:
            conn = self.get_db_connection()
            if not conn: return
            cursor = conn.cursor()

            execute(cursor, 'SELECT MIN("Data_Venda") AS "prim", MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            res_datas = cursor.fetchone()
            d_prim, d_ult = res_datas['prim'], res_datas['ult']

            if not d_prim:
                messagebox.showwarning("Aviso", "Banco vazio. Utilize o Gera Vendas Recentes primeiro.")
                return

            total_dias = (d_ult - d_prim).days + 1
            execute(cursor, 'SELECT COUNT(*) AS "c" FROM "Pedidos"')
            total_p = cursor.fetchone()['c']
            execute(cursor, 'SELECT COUNT(*) AS "c" FROM "PedItem"')
            total_i = cursor.fetchone()['c']

            media_p = round(total_p / total_dias) if total_dias > 0 else 0
            media_i = round(total_i / total_dias) if total_dias > 0 else 0
            media_itens_por_pedido = total_i / total_p if total_p > 0 else 2.0
            conn.close()

            win = tk.Toplevel(self.root)
            win.title("Confirmação Atualização Histórica")
            win.geometry("600x450")
            win.transient(self.root); win.grab_set()

            cont = ttk.Frame(win, padding="20"); cont.pack(fill="both", expand=True)
            header = ttk.Frame(cont); header.pack(fill="x", pady=5)
            ttk.Label(header, text=f"Data Primeira Venda: {d_prim.strftime('%d/%m/%Y')}", font=("Helvetica", 9, "bold")).pack(side="left")
            ttk.Label(header, text=f"Data Última Venda: {d_ult.strftime('%d/%m/%Y')}", font=("Helvetica", 9, "bold")).pack(side="right")

            lbl_stats = f"\nNúmero total de dias: {total_dias}\nNúmero Total de Pedidos: {total_p}\nNúmero Total de Itens: {total_i}"
            ttk.Label(cont, text=lbl_stats, justify="left").pack(anchor="w", pady=10)

            stats_frame = ttk.LabelFrame(cont, text=" Médias Diárias Arredondadas ", padding=15)
            stats_frame.pack(fill="x", pady=20)
            ttk.Label(stats_frame, text=f"Média Pedidos/Dia: {media_p}", font=("Helvetica", 10, "bold"), foreground="blue").pack(side="left", padx=20)
            ttk.Label(stats_frame, text=f"Média Itens/Dia: {media_i}", font=("Helvetica", 10, "bold"), foreground="blue").pack(side="right", padx=20)

            def confirmar():
                win.destroy()
                self.executar_historico(d_ult, media_p, media_itens_por_pedido)

            btn_f = ttk.Frame(cont); btn_f.pack(side="bottom", fill="x", pady=10)
            ttk.Button(btn_f, text="Confirmar", width=15, command=confirmar).pack(side="left")
            ttk.Button(btn_f, text="Cancelar", width=15, command=win.destroy).pack(side="right")
        except Exception as e:
            messagebox.showerror("Erro", f"Erro ao processar estatísticas:\n{e}")

    def executar_historico(self, d_ult, media_p, media_i_p):
        try:
            conn = self.get_db_connection()
            if not conn: return
            cursor = conn.cursor()
            inicio = d_ult + timedelta(days=1)
            hoje = datetime.now().date()
            total_pedidos_gerados = 0

            while inicio <= hoje:
                vol = self.calcular_volume(inicio, media_p)
                if vol > 0:
                    total_pedidos_gerados += vol
                    self.gerar_vendas(cursor, inicio, vol, media_i_p)
                inicio += timedelta(days=1)

            conn.commit()
            self.log(f"Carga Histórica: {total_pedidos_gerados} pedidos inseridos com sucesso.")
            messagebox.showinfo("Sucesso", f"Foram gerados {total_pedidos_gerados} pedidos históricos.")
        except Exception as e:
            self.log(f"Erro no Histórico: {e}")
        finally:
            if 'conn' in locals() and conn: conn.close()

    # --- 2. GERA VENDAS RECENTES (Conforme Especificações item 3) ---
    def abrir_cdc(self):
        try:
            conn = self.get_db_connection(); cursor = conn.cursor()
            execute(cursor, 'SELECT MIN("Data_Venda") AS "prim", MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            res_db = cursor.fetchone()
            # REGRA SOLICITADA: Sugestão da Data da Venda = Data da Última venda + 1 dia
            if res_db['ult']:
                d_ult = res_db['ult'] + timedelta(days=1)
            else:
                d_ult = datetime.now().date()
            total_dias = (res_db['ult'] - res_db['prim']).days + 1 if res_db['prim'] else 1
            execute(cursor, 'SELECT COUNT(*) AS "c" FROM "Pedidos"')
            media_sugerida = round(cursor.fetchone()['c'] / total_dias) if res_db['prim'] else 50
            conn.close()
        except Exception:
            d_ult = datetime.now().date(); media_sugerida = 50

        win = tk.Toplevel(self.root); win.title("Gera Vendas Recentes"); win.geometry("550x350")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        ttk.Label(f_frame, text="Data da Venda (Sugestão Última):").pack(anchor="w", pady=5)
        ent_d = ttk.Entry(f_frame); ent_d.insert(0, str(d_ult)); ent_d.pack(fill="x")
        ttk.Label(f_frame, text="Número de Pedidos (Média):").pack(anchor="w", pady=5)
        ent_m = ttk.Entry(f_frame); ent_m.insert(0, str(media_sugerida)); ent_m.pack(fill="x")

        def run():
            try:
                m_val = float(ent_m.get())
                dt = datetime.strptime(ent_d.get(), "%Y-%m-%d").date()
                conn = self.get_db_connection(); cursor = conn.cursor()

                execute(cursor, 'SELECT (SELECT COUNT(*) FROM "PedItem") AS "i", (SELECT COUNT(*) FROM "Pedidos") AS "p" FROM DUAL')
                r = cursor.fetchone()
                media_i_p = r['i'] / r['p'] if r['p'] > 0 else 2.0

                vol = self.calcular_volume(dt, m_val)
                self.gerar_vendas(cursor, dt, vol, media_i_p)
                conn.commit()
                self.log(f"Vendas recentes {dt}: {vol} pedidos gerados.")
                messagebox.showinfo("Sucesso", f"Total: {vol} pedidos.", parent=win)
                win.destroy()
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=win)
            finally:
                if 'conn' in locals() and conn: conn.close()

        ttk.Button(b_frame, text="Executar", width=20, command=run).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=20, command=win.destroy).pack(side="bottom", pady=5)

    # --- 3. CANCELAR PEDIDOS ---
    def abrir_cancelar_pedidos(self):
        try:
            conn = self.get_db_connection(); cursor = conn.cursor()
            execute(cursor, 'SELECT MIN("Data_Venda") AS "prim", MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            res = cursor.fetchone()
            d_ini = res['prim'] or datetime.now().date() - timedelta(days=60)
            d_ult = res['ult'] or datetime.now().date()
            conn.close()
        except Exception:
            d_ini = datetime.now().date() - timedelta(days=60)
            d_ult = datetime.now().date()

        win = tk.Toplevel(self.root); win.title("Cancelar Pedidos"); win.geometry("550x320")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        entries = {}
        labels = [("Data Inicial", d_ini), ("Data Final", d_ult), ("Probabilidade (0-100)", "60")]
        for txt, val in labels:
            ttk.Label(f_frame, text=f"{txt}:").pack(anchor="w")
            ent = ttk.Entry(f_frame)
            ent.insert(0, str(val))
            ent.pack(fill="x", pady=2)
            entries[txt] = ent

        def executar():
            try:
                di_str = entries["Data Inicial"].get().strip()
                df_str = entries["Data Final"].get().strip()
                prob_str = entries["Probabilidade (0-100)"].get().strip()

                if not di_str or not df_str or not prob_str:
                    raise ValueError("Preencha todos os campos.")

                di = datetime.strptime(di_str, "%Y-%m-%d").date()
                df = datetime.strptime(df_str, "%Y-%m-%d").date()
                prob = float(prob_str) / 100.0

                if di > df:
                    raise ValueError("A Data Inicial não pode ser maior que a Data Final.")

                conn = self.get_db_connection(); cursor = conn.cursor()
                execute(cursor, """
                    UPDATE "Pedidos"
                    SET "Cancelado" = 1,
                        "Data_Remessa" = NULL
                    WHERE "Cancelado" = 0
                      AND "Data_Venda" BETWEEN :di AND :df
                      AND DBMS_RANDOM.VALUE < :prob
                """, {'di': to_bind_date(di), 'df': to_bind_date(df), 'prob': prob})
                conn.commit()
                self.log(f"Cancelamento: {cursor.rowcount} pedidos alterados para cancelados no período {di} a {df}.")
                messagebox.showinfo("Sucesso", f"{cursor.rowcount} pedidos foram cancelados.", parent=win)
                win.destroy()
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=win)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=win)
            finally:
                if 'conn' in locals() and conn: conn.close()

        ttk.Button(b_frame, text="Cancelar", width=15, command=executar).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=15, command=win.destroy).pack(side="bottom", pady=5)

    # --- 5. GERA DEVOLUÇÕES ---
    def abrir_gerar_devolucoes(self):
        try:
            conn = self.get_db_connection(); cursor = conn.cursor()
            execute(cursor, 'SELECT MIN("Data_Venda") AS "prim", MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            res = cursor.fetchone()
            d_ini = res['prim'] or datetime.now().date() - timedelta(days=60)
            d_ult = res['ult'] or datetime.now().date()
            conn.close()
        except Exception:
            d_ini = datetime.now().date() - timedelta(days=60)
            d_ult = datetime.now().date()

        win = tk.Toplevel(self.root); win.title("Gerar Devoluções"); win.geometry("650x420")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        entries = {}
        labels = [
            ("Data Inicial", d_ini),
            ("Data Final", d_ult),
            ("Probabilidade de Pedido (0-100)", "2"),
            ("Probabilidade de Itens (0-100)", "100"),
            ("Probabilidade de Qtde (0-100)", "100"),
            ("Dias para devolução", "7")
        ]
        for txt, val in labels:
            ttk.Label(f_frame, text=f"{txt}:").pack(anchor="w", pady=(6, 2))
            ent = ttk.Entry(f_frame)
            ent.insert(0, str(val))
            ent.pack(fill="x")
            entries[txt] = ent

        def executar():
            try:
                di_str = entries["Data Inicial"].get().strip()
                df_str = entries["Data Final"].get().strip()
                prob_pedido_str = entries["Probabilidade de Pedido (0-100)"].get().strip()
                prob_itens_str = entries["Probabilidade de Itens (0-100)"].get().strip()
                prob_qtde_str = entries["Probabilidade de Qtde (0-100)"].get().strip()
                dias_str = entries["Dias para devolução"].get().strip()

                if not all([di_str, df_str, prob_pedido_str, prob_itens_str, prob_qtde_str, dias_str]):
                    raise ValueError("Preencha todos os campos.")

                di = datetime.strptime(di_str, "%Y-%m-%d").date()
                df = datetime.strptime(df_str, "%Y-%m-%d").date()
                if di > df:
                    raise ValueError("A Data Inicial não pode ser maior que a Data Final.")

                prob_pedido = float(prob_pedido_str) / 100.0
                prob_itens = float(prob_itens_str) / 100.0
                prob_qtde = float(prob_qtde_str) / 100.0
                dias_dev = int(dias_str)

                if not 0 <= prob_pedido <= 1 or not 0 <= prob_itens <= 1 or not 0 <= prob_qtde <= 1:
                    raise ValueError("As probabilidades devem estar entre 0 e 100%.")
                if dias_dev < 0:
                    raise ValueError("Os dias para devolução não podem ser negativos.")

                conn = self.get_db_connection()
                if not conn:
                    return
                cursor = conn.cursor()
                total_devolucoes, total_itens = self.gerar_devolucoes(
                    cursor,
                    di,
                    df,
                    prob_pedido,
                    prob_itens,
                    prob_qtde,
                    dias_dev,
                )
                conn.commit()
                self.log(f"Devoluções: {total_devolucoes} cabeçalhos e {total_itens} itens criados no período {di} a {df}.")
                messagebox.showinfo("Sucesso", f"Foram criadas {total_devolucoes} devoluções com {total_itens} itens.", parent=win)
                win.destroy()
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=win)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=win)
            finally:
                if 'conn' in locals() and conn: conn.close()

        ttk.Button(b_frame, text="Executar", width=18, command=executar).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=18, command=win.destroy).pack(side="bottom", pady=5)

    def gerar_devolucoes(self, cursor, data_ini, data_fim, prob_pedido, prob_itens, prob_qtde, dias_dev):
        """Gera devoluções para pedidos elegíveis no período informado."""
        execute(cursor, """
            SELECT p."Pedido_ID" AS "Pedido_ID", p."Data_Remessa" AS "Data_Remessa",
                   pi."PedItem_ID" AS "PedItem_ID", pi."Produto_ID" AS "Produto_ID",
                   pi."Qtde_Venda" AS "Qtde_Venda", pi."PrecoUN_Venda" AS "PrecoUN_Venda"
            FROM "Pedidos" p
            JOIN "PedItem" pi ON pi."Pedido_ID" = p."Pedido_ID"
            WHERE p."Data_Venda" BETWEEN :di AND :df
              AND p."Cancelado" = 0
              AND p."Data_Remessa" IS NOT NULL
            ORDER BY p."Pedido_ID", pi."PedItem_ID"
        """, {'di': to_bind_date(data_ini), 'df': to_bind_date(data_fim)})
        linhas = cursor.fetchall()

        if not linhas:
            return 0, 0

        execute(cursor, """
            SELECT di."PedItem_ID" AS "PedItem_ID", SUM(di."Qtde_Devolvida") AS "total_dev"
            FROM "Devolucao_Item" di
            JOIN "Devolucoes" d ON d."Devolucao_ID" = di."Devolucao_ID"
            GROUP BY di."PedItem_ID"
        """)
        devolucoes_existentes = {}
        for item in cursor.fetchall():
            devolucoes_existentes[int(item['PedItem_ID'])] = int(item['total_dev'] or 0)

        pedidos = {}
        for row in linhas:
            pedidos.setdefault(int(row['Pedido_ID']), []).append({
                'PedItem_ID': int(row['PedItem_ID']),
                'Produto_ID': int(row['Produto_ID']),
                'Qtde_Venda': int(row['Qtde_Venda']),
                'PrecoUN_Venda': float(row['PrecoUN_Venda'] or 0),
                'Data_Remessa': row['Data_Remessa']
            })

        total_devolucoes = 0
        total_itens = 0

        for pedido_id, itens in pedidos.items():
            if random.random() >= prob_pedido:
                continue

            if all(devolucoes_existentes.get(item['PedItem_ID'], 0) >= item['Qtde_Venda'] for item in itens):
                continue

            data_devolucao = itens[0]['Data_Remessa'] + timedelta(days=dias_dev)

            # "Devolucao_ID" NAO e informado - trigger TRG_DEVOLUCOES_ID atribui via
            # SEQ_DEVOLUCOES_ID.NEXTVAL quando a coluna vem NULL. RETURNING recupera
            # o valor gerado (equivalente ao cursor.lastrowid do pymysql/MySQL).
            out_id = cursor.var(oracledb.NUMBER)
            cursor.execute(
                """
                INSERT INTO "Devolucoes" ("Pedido_ID", "Data_Devolucao", "Observacao")
                VALUES (:pedido_id, :data_devolucao, :observacao)
                RETURNING "Devolucao_ID" INTO :out_id
                """,
                {
                    'pedido_id': pedido_id,
                    'data_devolucao': to_bind_date(data_devolucao),
                    'observacao': 'Gerado automaticamente pelo GenerateData',
                    'out_id': out_id,
                }
            )
            devolucao_id = int(out_id.getvalue()[0])
            total_devolucoes += 1

            for item in itens:
                devolvido = devolucoes_existentes.get(item['PedItem_ID'], 0)
                restante = item['Qtde_Venda'] - devolvido
                if restante <= 0:
                    continue

                if random.random() >= prob_itens:
                    continue

                qtd_devolvida = calcular_quantidade_devolucao(
                    restante,
                    prob_qtde,
                    random.random(),
                )
                if qtd_devolvida <= 0:
                    continue

                # "Valor_Devolucao" NAO e informado - trigger TRG_DEVOLUCAO_ITEM_VALOR
                # calcula Qtde_Devolvida * PrecoUN_Venda automaticamente (equivalente
                # a coluna gerada do MySQL). "Devolucao_Item_ID" tambem omitido -
                # gerado pelo mesmo padrao SEQUENCE + TRIGGER (SEQ_DEVOLUCAO_ITEM_ID).
                cursor.execute(
                    """
                    INSERT INTO "Devolucao_Item" (
                        "Devolucao_ID", "PedItem_ID", "Produto_ID", "Qtde_Devolvida", "PrecoUN_Venda"
                    ) VALUES (:devolucao_id, :peditem_id, :produto_id, :qtde_devolvida, :preco_un_venda)
                    """,
                    {
                        'devolucao_id': devolucao_id,
                        'peditem_id': item['PedItem_ID'],
                        'produto_id': item['Produto_ID'],
                        'qtde_devolvida': qtd_devolvida,
                        'preco_un_venda': item['PrecoUN_Venda'],
                    }
                )
                devolucoes_existentes[item['PedItem_ID']] = devolvido + qtd_devolvida
                total_itens += 1

        return total_devolucoes, total_itens

    # --- 3. APAGAR REGISTROS (Conforme Especificações item 4) ---
    def abrir_apagar_registros(self):
        try:
            conn = self.get_db_connection(); cursor = conn.cursor()
            execute(cursor, 'SELECT MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            d_ult = cursor.fetchone()['ult']
            conn.close()
        except Exception:
            d_ult = datetime.now().date()

        win = tk.Toplevel(self.root); win.title("Apagar Registros"); win.geometry("450x250")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        ttk.Label(f_frame, text="Data da Venda a Eliminar:").pack(anchor="w")
        ent_d = ttk.Entry(f_frame); ent_d.insert(0, str(d_ult)); ent_d.pack(fill="x", pady=5)

        def eliminar():
            if messagebox.askyesno("Confirmar", f"Apagar registros de {ent_d.get()}?", parent=win):
                try:
                    dt = datetime.strptime(ent_d.get(), "%Y-%m-%d").date()
                    conn = self.get_db_connection(); cursor = conn.cursor()
                    p_dt = to_bind_date(dt)

                    execute(cursor, """
                        SELECT COUNT(*) AS "total"
                        FROM "Devolucoes"
                        WHERE "Pedido_ID" IN (
                            SELECT "Pedido_ID" FROM "Pedidos" WHERE "Data_Venda" = :dt
                        )
                    """, {'dt': p_dt})
                    dv = cursor.fetchone()['total'] or 0

                    execute(cursor, """
                        SELECT COUNT(*) AS "total"
                        FROM "Devolucao_Item"
                        WHERE "Devolucao_ID" IN (
                            SELECT "Devolucao_ID"
                            FROM "Devolucoes"
                            WHERE "Pedido_ID" IN (
                                SELECT "Pedido_ID" FROM "Pedidos" WHERE "Data_Venda" = :dt
                            )
                        )
                    """, {'dt': p_dt})
                    di = cursor.fetchone()['total'] or 0

                    if dv > 0:
                        execute(cursor, """
                            DELETE FROM "Devolucao_Item"
                            WHERE "Devolucao_ID" IN (
                                SELECT "Devolucao_ID"
                                FROM "Devolucoes"
                                WHERE "Pedido_ID" IN (
                                    SELECT "Pedido_ID" FROM "Pedidos" WHERE "Data_Venda" = :dt
                                )
                            )
                        """, {'dt': p_dt})

                        execute(cursor, """
                            DELETE FROM "Devolucoes"
                            WHERE "Pedido_ID" IN (
                                SELECT "Pedido_ID" FROM "Pedidos" WHERE "Data_Venda" = :dt
                            )
                        """, {'dt': p_dt})

                    execute(cursor, """
                        DELETE FROM "PedItem"
                        WHERE "Pedido_ID" IN (
                            SELECT "Pedido_ID" FROM "Pedidos" WHERE "Data_Venda" = :dt
                        )
                    """, {'dt': p_dt})
                    it = cursor.rowcount

                    execute(cursor, 'DELETE FROM "Pedidos" WHERE "Data_Venda" = :dt', {'dt': p_dt})
                    pe = cursor.rowcount
                    conn.commit()
                    self.log(f"Remoção {dt}: {pe} pedidos, {it} itens e {dv} devoluções ({di} itens de devolução) removidos.")
                    win.destroy()
                except Exception as e:
                    messagebox.showerror("Erro", str(e), parent=win)
                finally:
                    if 'conn' in locals() and conn: conn.close()

        ttk.Button(b_frame, text="Eliminar", width=15, command=eliminar).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=15, command=win.destroy).pack(side="bottom", pady=5)

    # --- 4. ATUALIZAR DATA REMESSA (Conforme Especificações item 5) ---
    def abrir_atualizar_remessa(self):
        try:
            conn = self.get_db_connection(); cursor = conn.cursor()
            execute(cursor, 'SELECT MAX("Data_Venda") AS "ult" FROM "Pedidos"')
            d_ult = cursor.fetchone()['ult']
            conn.close()
        except Exception:
            d_ult = datetime.now().date()

        if d_ult is None:
            d_ult = datetime.now().date()

        win = tk.Toplevel(self.root); win.title("Data Remessa"); win.geometry("600x400")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        entries = {}
        labels = [("Data Final", d_ult), ("Intervalo Inicial (dias)", "1"), ("Intervalo Final (dias)", "20")]
        for txt, val in labels:
            ttk.Label(f_frame, text=f"{txt}:").pack(anchor="w")
            ent = ttk.Entry(f_frame); ent.insert(0, str(val)); ent.pack(fill="x", pady=2)
            entries[txt] = ent

        def executar():
            try:
                data_final_str = entries["Data Final"].get().strip()
                ini_str = entries["Intervalo Inicial (dias)"].get().strip()
                fim_str = entries["Intervalo Final (dias)"].get().strip()

                if not data_final_str:
                    raise ValueError("Informe a Data Final.")

                data_final = datetime.strptime(data_final_str, "%Y-%m-%d").date()
                ini = int(ini_str)
                fim = int(fim_str)

                if ini > fim:
                    raise ValueError("O intervalo inicial não pode ser maior que o final.")

                conn = self.get_db_connection()
                if not conn:
                    return
                cursor = conn.cursor()

                execute(cursor, """
                    SELECT "Pedido_ID" AS "Pedido_ID", "Data_Venda" AS "Data_Venda"
                    FROM "Pedidos"
                    WHERE "Data_Remessa" IS NULL
                      AND "Cancelado" = 0
                      AND "Data_Venda" <= :data_final
                    ORDER BY "Data_Venda", "Pedido_ID"
                """, {'data_final': to_bind_date(data_final)})
                pedidos = cursor.fetchall()

                atualizados = 0
                for pedido in pedidos:
                    dias = random.randint(ini, fim)
                    data_remessa = pedido['Data_Venda'] + timedelta(days=dias)
                    execute(cursor,
                        'UPDATE "Pedidos" SET "Data_Remessa" = :data_remessa WHERE "Pedido_ID" = :pedido_id',
                        {'data_remessa': to_bind_date(data_remessa), 'pedido_id': pedido['Pedido_ID']}
                    )
                    atualizados += 1

                conn.commit()
                self.log(f"Remessa: {atualizados} pedidos atualizados até {data_final} com intervalo de {ini}-{fim} dias.")
                messagebox.showinfo("Sucesso", f"{atualizados} registros atualizados.", parent=win)
                win.destroy()
            except ValueError as e:
                messagebox.showerror("Erro", str(e), parent=win)
            except Exception as e:
                messagebox.showerror("Erro", str(e), parent=win)
            finally:
                if 'conn' in locals() and conn: conn.close()

        ttk.Button(b_frame, text="Atualizar", width=15, command=executar).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=15, command=win.destroy).pack(side="bottom", pady=5)

    # --- 5. CONFIGURA CONEXÃO (Conforme Especificações item 5) ---
    def abrir_configuracao(self):
        win = tk.Toplevel(self.root); win.title("Conexão Oracle"); win.geometry("650x480")
        win.transient(self.root); win.grab_set()
        f_frame = ttk.Frame(win, padding="15"); f_frame.pack(side="left", fill="both", expand=True)
        b_frame = ttk.Frame(win, padding="15"); b_frame.pack(side="right", fill="y")

        defaults = {'host': 'localhost', 'port': '1521', 'service_name': 'XEPDB1', 'user': 'vendasods'}
        fields = [
            ("Host", "host"),
            ("Porta", "port"),
            ("Service Name", "service_name"),
            ("Usuário (schema)", "user"),
            ("Senha", "password_raw"),
        ]
        entries = {}
        for label, key in fields:
            ttk.Label(f_frame, text=f"{label}:").pack(anchor="w")
            ent = ttk.Entry(f_frame, show="*" if "Senha" in label else "")
            ent.pack(fill="x", pady=5)
            if self.db_config and key in self.db_config:
                ent.insert(0, self.db_config[key])
            elif key in defaults:
                ent.insert(0, defaults[key])
            entries[key] = ent

        def testar():
            try:
                dsn = oracledb.makedsn(
                    entries['host'].get(),
                    int(entries['port'].get()),
                    service_name=entries['service_name'].get()
                )
                c = oracledb.connect(
                    user=entries['user'].get(),
                    password=entries['password_raw'].get(),
                    dsn=dsn
                )
                messagebox.showinfo("Sucesso", "Conexão estabelecida com sucesso!", parent=win); c.close()
            except Exception as e:
                messagebox.showerror("Erro", f"Falha: {e}", parent=win)

        def salvar():
            data = {k: v.get() for k, v in entries.items()}
            data['password_encrypted'] = encrypt_password(data['password_raw'])
            with open(self.config_file, 'w', encoding='utf-8') as f:
                yaml.dump(data, f)
            self.db_config = data
            messagebox.showinfo("Sucesso", "Configuração gravada no arquivo YAML!", parent=win)
            win.destroy()

        ttk.Button(b_frame, text="Testar Conexão", width=20, command=testar).pack(pady=5)
        ttk.Button(b_frame, text="Gravar", width=20, command=salvar).pack(pady=5)
        ttk.Button(b_frame, text="Sair", width=20, command=win.destroy).pack(side="bottom", pady=5)

    # --- 6. ATUALIZA TABELAS (Conforme Solicitação) ---
    def abrir_atualiza_tabelas(self):
        try:
            conn = self.get_db_connection()
            cursor = conn.cursor()
            # Busca a última data de período na TabPreco para sugestão
            execute(cursor, 'SELECT MAX("Periodo") AS "ult" FROM "TabPreco"')
            res = cursor.fetchone()
            ult_periodo = res['ult'] if res and res['ult'] else None
            conn.close()

            if ult_periodo:
                # Calcula o primeiro dia do mês subsequente
                if ult_periodo.month == 12:
                    prox_mes = ult_periodo.replace(year=ult_periodo.year + 1, month=1, day=1)
                else:
                    prox_mes = ult_periodo.replace(month=ult_periodo.month + 1, day=1)
            else:
                prox_mes = datetime.now().date().replace(day=1)
        except Exception:
            prox_mes = datetime.now().date().replace(day=1)

        win = tk.Toplevel(self.root)
        win.title("Atualiza Tabelas (Frete e Preço)")
        win.geometry("550x300")
        win.transient(self.root)
        win.grab_set()

        f_frame = ttk.Frame(win, padding="15")
        f_frame.pack(side="top", fill="both", expand=True)

        # Campos de Entrada
        campos = [
            ("Período (AAAA-MM-DD):", str(prox_mes)),
            ("% Aumento/Redução Perc_Frete:", "0"),
            ("% Aumento/Redução Preço Venda:", "0"),
            ("% Aumento/Redução Preço Custo:", "0")
        ]

        self.entries_tabelas = {}
        for idx, (label_text, default_val) in enumerate(campos):
            ttk.Label(f_frame, text=label_text).grid(row=idx, column=0, sticky="w", pady=8)
            ent = ttk.Entry(f_frame)
            ent.insert(0, default_val)
            ent.grid(row=idx, column=1, sticky="ew", pady=8, padx=10)
            self.entries_tabelas[label_text] = ent

        f_frame.columnconfigure(1, weight=1)

        b_frame = ttk.Frame(win, padding="15")
        b_frame.pack(side="bottom", fill="x")

        def confirmar():
            try:
                periodo_str = self.entries_tabelas["Período (AAAA-MM-DD):"].get()
                novo_periodo = datetime.strptime(periodo_str, "%Y-%m-%d").date()

                if novo_periodo.day != 1:
                    messagebox.showwarning("Aviso", "O campo Período deve conter o primeiro dia do mês.", parent=win)
                    return

                p_frete = float(self.entries_tabelas["% Aumento/Redução Perc_Frete:"].get()) / 100.0
                p_venda = float(self.entries_tabelas["% Aumento/Redução Preço Venda:"].get()) / 100.0
                p_custo = float(self.entries_tabelas["% Aumento/Redução Preço Custo:"].get()) / 100.0

                self.executar_atualiza_tabelas(novo_periodo, p_frete, p_venda, p_custo, win)
            except ValueError:
                messagebox.showerror("Erro", "Certifique-se de inserir uma data válida e valores numéricos para os percentuais.", parent=win)

        ttk.Button(b_frame, text="Confirmar", width=15, command=confirmar).pack(side="left", padx=20)
        ttk.Button(b_frame, text="Cancelar", width=15, command=win.destroy).pack(side="right", padx=20)

    def executar_atualiza_tabelas(self, novo_periodo, p_frete, p_venda, p_custo, win):
        conn = self.get_db_connection()
        if not conn: return
        try:
            cursor = conn.cursor()
            p_periodo = to_bind_date(novo_periodo)

            # Evita duplicação de chave primária limpando registros do período alvo caso existam
            execute(cursor, 'DELETE FROM "TabPreco" WHERE "Periodo" = :periodo', {'periodo': p_periodo})
            execute(cursor, 'DELETE FROM "TabFrete" WHERE "Periodo" = :periodo', {'periodo': p_periodo})

            linhas_preco, linhas_frete = 0, 0

            # 1. Processar TabPreco
            execute(cursor, 'SELECT MAX("Periodo") AS "ult_p" FROM "TabPreco" WHERE "Periodo" < :periodo', {'periodo': p_periodo})
            ult_p_preco = cursor.fetchone()['ult_p']

            if ult_p_preco:
                execute(cursor,
                    'SELECT "Produto_ID" AS "Produto_ID", "PrecoUN_Venda" AS "PrecoUN_Venda", "PrecoUN_Custo" AS "PrecoUN_Custo" '
                    'FROM "TabPreco" WHERE "Periodo" = :periodo',
                    {'periodo': to_bind_date(ult_p_preco)}
                )
                regs_preco = cursor.fetchall()
                for r in regs_preco:
                    n_venda = round(float(r['PrecoUN_Venda'] or 0) * (1.0 + p_venda), 2)
                    n_custo = round(float(r['PrecoUN_Custo'] or 0) * (1.0 + p_custo), 2)
                    execute(cursor,
                        'INSERT INTO "TabPreco" ("Produto_ID", "Periodo", "PrecoUN_Venda", "PrecoUN_Custo") '
                        'VALUES (:produto_id, :periodo, :preco_venda, :preco_custo)',
                        {'produto_id': r['Produto_ID'], 'periodo': p_periodo, 'preco_venda': n_venda, 'preco_custo': n_custo}
                    )
                linhas_preco = len(regs_preco)

            # 2. Processar TabFrete
            execute(cursor, 'SELECT MAX("Periodo") AS "ult_p" FROM "TabFrete" WHERE "Periodo" < :periodo', {'periodo': p_periodo})
            ult_p_frete = cursor.fetchone()['ult_p']

            if ult_p_frete:
                execute(cursor,
                    'SELECT "Cidade_ID" AS "Cidade_ID", "Perc_Frete" AS "Perc_Frete" FROM "TabFrete" WHERE "Periodo" = :periodo',
                    {'periodo': to_bind_date(ult_p_frete)}
                )
                regs_frete = cursor.fetchall()
                for r in regs_frete:
                    n_frete = round(float(r['Perc_Frete'] or 0) * (1.0 + p_frete), 2)
                    execute(cursor,
                        'INSERT INTO "TabFrete" ("Cidade_ID", "Periodo", "Perc_Frete") VALUES (:cidade_id, :periodo, :perc_frete)',
                        {'cidade_id': r['Cidade_ID'], 'periodo': p_periodo, 'perc_frete': n_frete}
                    )
                linhas_frete = len(regs_frete)

            conn.commit()

            # Exibir Mensagens de Conclusão
            msg = f"Tabelas atualizadas com sucesso para {novo_periodo}:\n\n- TabPreco: {linhas_preco} registros criados.\n- TabFrete: {linhas_frete} registros criados."
            self.log(msg.replace("\n\n", " | ").replace("\n", " "))
            messagebox.showinfo("Sucesso", msg, parent=win)
            win.destroy()

        except Exception as e:
            conn.rollback()
            messagebox.showerror("Erro BD", f"Falha ao executar rotina:\n{e}", parent=win)
            self.log(f"Erro Atualiza Tabelas: {e}")
        finally:
            conn.close()

    # --- MOTOR DE GERAÇÃO E LÓGICA DE NEGÓCIO ---
    def calcular_volume(self, data, media):
        """Aplica pesos: Semana 100%, Sáb 60%, Dom 0%. Variação de +-10%."""
        wd = data.weekday() # 0=Seg... 5=Sáb, 6=Dom
        if wd == 6: return 0
        peso = 0.6 if wd == 5 else 1.0
        return int(random.uniform(media * peso * 0.9, media * peso * 1.1))

    def gerar_vendas(self, cursor, data, qtd_pedidos, m_i_p):
        """Gera X pedidos e assegura que cada um terá pelo menos um item válido."""
        execute(cursor,
            'SELECT c."Cliente_ID" AS "Cliente_ID", c."Cidade_ID" AS "Cidade_ID" '
            'FROM "Clientes" c WHERE EXISTS (SELECT 1 FROM "Vendedores" v WHERE v."Cidade_ID" = c."Cidade_ID")'
        )
        clis = cursor.fetchall()

        periodo = data.replace(day=1)
        p_periodo = to_bind_date(periodo)

        # FILTRO CRÍTICO: Buscar apenas produtos que tenham preço para o período atual
        execute(cursor, 'SELECT "Produto_ID" AS "Produto_ID" FROM "TabPreco" WHERE "Periodo" = :periodo', {'periodo': p_periodo})
        prods_com_preco = [row['Produto_ID'] for row in cursor.fetchall()]

        if not prods_com_preco:
            self.log(f"Aviso: Nenhum preço encontrado na TabPreco para {periodo}. Pulando geração para {data}.")
            return

        execute(cursor, 'SELECT NVL(MAX("Pedido_ID"), 0) + 1 AS "n" FROM "Pedidos"'); nid_p = int(cursor.fetchone()['n'])
        execute(cursor, 'SELECT NVL(MAX("PedItem_ID"), 0) + 1 AS "n" FROM "PedItem"'); nid_i = int(cursor.fetchone()['n'])

        for _ in range(qtd_pedidos):
            cli = random.choice(clis)
            execute(cursor,
                'SELECT "Vendedor_ID" AS "Vendedor_ID" FROM "Vendedores" WHERE "Cidade_ID" = :cidade_id FETCH FIRST 1 ROW ONLY',
                {'cidade_id': int(cli['Cidade_ID'])}
            )
            vid = cursor.fetchone()['Vendedor_ID']
            execute(cursor,
                'SELECT "Perc_Frete" AS "f" FROM "TabFrete" WHERE "Cidade_ID" = :cidade_id AND "Periodo" = :periodo',
                {'cidade_id': int(cli['Cidade_ID']), 'periodo': p_periodo}
            )
            pf = float((cursor.fetchone() or {'f': 0})['f'] or 0)

            # "Periodo" tambem e recalculada por TRG_PEDIDOS_PERIODO a partir de
            # Data_Venda - o valor enviado aqui e redundante mas consistente.
            execute(cursor,
                'INSERT INTO "Pedidos" ("Pedido_ID", "Cliente_ID", "Vendedor_ID", "Data_Venda", "Periodo", "Perc_Frete", "Cancelado") '
                'VALUES (:pedido_id, :cliente_id, :vendedor_id, :data_venda, :periodo, :perc_frete, 0)',
                {
                    'pedido_id': nid_p,
                    'cliente_id': int(cli['Cliente_ID']),
                    'vendedor_id': vid,
                    'data_venda': to_bind_date(data),
                    'periodo': p_periodo,
                    'perc_frete': pf,
                }
            )

            # Garantia de pelo menos 1 item e no máximo a média calculada
            num_it = max(1, int(random.uniform(m_i_p - 0.5, m_i_p + 1.5)))
            for _ in range(num_it):
                pid = random.choice(prods_com_preco) # Escolhe apenas produtos que sabidamente têm preço
                execute(cursor,
                    'SELECT "PrecoUN_Venda" AS "PrecoUN_Venda", "PrecoUN_Custo" AS "PrecoUN_Custo" '
                    'FROM "TabPreco" WHERE "Produto_ID" = :produto_id AND "Periodo" = :periodo',
                    {'produto_id': pid, 'periodo': p_periodo}
                )
                pr = cursor.fetchone()
                if pr:
                    v, c, q = float(pr['PrecoUN_Venda'] or 0), float(pr['PrecoUN_Custo'] or 0), float(random.randint(1, 5))
                    execute(cursor,
                        'INSERT INTO "PedItem" ("PedItem_ID", "Pedido_ID", "Produto_ID", "Qtde_Venda", "Valor_Venda", '
                        '"Valor_Custo", "Valor_Frete", "Valor_Margem", "PrecoUN_Venda", "PrecoUN_Custo") '
                        'VALUES (:peditem_id, :pedido_id, :produto_id, :qtde_venda, :valor_venda, :valor_custo, '
                        ':valor_frete, :valor_margem, :preco_un_venda, :preco_un_custo)',
                        {
                            'peditem_id': nid_i,
                            'pedido_id': nid_p,
                            'produto_id': int(pid),
                            'qtde_venda': int(q),
                            'valor_venda': v * q,
                            'valor_custo': c * q,
                            'valor_frete': (v * q) * (pf / 100.0),
                            'valor_margem': (v * q) - (c * q),
                            'preco_un_venda': v,
                            'preco_un_custo': c,
                        }
                    )
                    nid_i += 1
            nid_p += 1

if __name__ == "__main__":
    root = tk.Tk()
    app = VendasODSApp(root)
    root.mainloop()
