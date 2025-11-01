import gc
import psutil
from sqlalchemy import create_engine
from configuracoes.config import CONFIGURACAO_BD

class GerenciadorBancoDados:
    def __init__(self):
        self._engine = None
        self._string_conexao = self._construir_string_conexao()
    
    def _construir_string_conexao(self) -> str:
        return (f"postgresql://{CONFIGURACAO_BD['user']}:{CONFIGURACAO_BD['password']}"
                f"@{CONFIGURACAO_BD['host']}:{CONFIGURACAO_BD['port']}/{CONFIGURACAO_BD['database']}")
    
    def obter_engine(self):
        if self._engine is None:
            try:
                self._engine = create_engine(
                    self._string_conexao,
                    pool_size=5,
                    max_overflow=10,
                    pool_pre_ping=True,
                    pool_recycle=3600,
                    echo=False
                )
            except Exception:
                return None
        return self._engine
    
    def liberar(self):
        if self._engine:
            self._engine.dispose()
            self._engine = None
            gc.collect()

def limpar_memoria_se_necessario():
    if psutil.virtual_memory().percent > 85:
        gc.collect()
