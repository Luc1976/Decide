-- Esquema SQLite do app em produção (branch main), antes do Alembic.
CREATE TABLE usuario (
	id INTEGER NOT NULL, 
	username VARCHAR NOT NULL, 
	senha VARCHAR NOT NULL, 
	nome_completo VARCHAR NOT NULL, 
	admin BOOLEAN NOT NULL, 
	pode_criar_projetos BOOLEAN NOT NULL, 
	PRIMARY KEY (id), 
	UNIQUE (username)
);

CREATE TABLE projeto (
	id INTEGER NOT NULL, 
	nome VARCHAR NOT NULL, 
	cliente VARCHAR NOT NULL, 
	descricao VARCHAR, 
	data_criacao DATETIME NOT NULL, 
	PRIMARY KEY (id)
);

CREATE TABLE membroprojeto (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	usuario_id INTEGER NOT NULL, 
	papel VARCHAR NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id), 
	FOREIGN KEY(usuario_id) REFERENCES usuario (id)
);

CREATE TABLE caracteristica (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	grupo VARCHAR NOT NULL, 
	nome VARCHAR NOT NULL, 
	valor VARCHAR NOT NULL, 
	unidade VARCHAR, 
	atualizado_por VARCHAR NOT NULL, 
	data_atualizacao DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id)
);

CREATE TABLE padraoconstrutivo (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	tipologia VARCHAR NOT NULL, 
	ind_estrutura VARCHAR, 
	ind_vedacao VARCHAR, 
	ind_carga_piso FLOAT, 
	ind_pavimento_externo VARCHAR, 
	multi_sistema_principal VARCHAR, 
	multi_tipo_laje VARCHAR, 
	corp_fachada VARCHAR, 
	dc_tier_redundancia VARCHAR, 
	shop_estrutura VARCHAR, 
	shop_cobertura VARCHAR, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id)
);

CREATE INDEX ix_padraoconstrutivo_projeto_id ON padraoconstrutivo (projeto_id);

CREATE TABLE reuniao (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	numero INTEGER NOT NULL, 
	titulo VARCHAR NOT NULL, 
	data_reuniao DATE NOT NULL, 
	participantes VARCHAR, 
	texto VARCHAR NOT NULL, 
	status VARCHAR NOT NULL, 
	autor VARCHAR NOT NULL, 
	data_fechamento DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id)
);

CREATE TABLE ataadendo (
	id INTEGER NOT NULL, 
	reuniao_id INTEGER NOT NULL, 
	texto VARCHAR NOT NULL, 
	autor VARCHAR NOT NULL, 
	data_registro DATETIME NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(reuniao_id) REFERENCES reuniao (id)
);

CREATE TABLE decisao (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	titulo VARCHAR NOT NULL, 
	categoria VARCHAR NOT NULL, 
	descricao VARCHAR NOT NULL, 
	justificativa VARCHAR NOT NULL, 
	alternativa_descartada VARCHAR, 
	impacto VARCHAR NOT NULL, 
	autor VARCHAR NOT NULL, 
	data_decisao DATE NOT NULL, 
	anexos VARCHAR, 
	checklist VARCHAR, 
	reuniao_id INTEGER, 
	numero INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id), 
	FOREIGN KEY(reuniao_id) REFERENCES reuniao (id)
);

CREATE TABLE caracteristicahistorico (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	grupo VARCHAR NOT NULL, 
	nome VARCHAR NOT NULL, 
	valor_anterior VARCHAR, 
	valor_novo VARCHAR, 
	autor VARCHAR NOT NULL, 
	data_registro DATETIME NOT NULL, 
	decisao_id INTEGER, 
	reuniao_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id), 
	FOREIGN KEY(decisao_id) REFERENCES decisao (id), 
	FOREIGN KEY(reuniao_id) REFERENCES reuniao (id)
);

CREATE TABLE pendencia (
	id INTEGER NOT NULL, 
	projeto_id INTEGER NOT NULL, 
	numero INTEGER NOT NULL, 
	titulo VARCHAR NOT NULL, 
	descricao VARCHAR NOT NULL, 
	categoria VARCHAR NOT NULL, 
	responsavel VARCHAR NOT NULL, 
	prazo DATE, 
	status VARCHAR NOT NULL, 
	autor VARCHAR NOT NULL, 
	data_criacao DATETIME NOT NULL, 
	reuniao_id INTEGER, 
	decisao_id INTEGER, 
	resolucao VARCHAR NOT NULL, 
	resolvida_por VARCHAR NOT NULL, 
	data_resolucao DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(projeto_id) REFERENCES projeto (id), 
	FOREIGN KEY(reuniao_id) REFERENCES reuniao (id), 
	FOREIGN KEY(decisao_id) REFERENCES decisao (id)
);

CREATE INDEX ix_pendencia_projeto_id ON pendencia (projeto_id);
