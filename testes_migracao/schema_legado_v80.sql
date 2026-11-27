-- Reprodução apenas estrutural do catálogo legado (27/11/2026).
-- Nenhum dado, senha, credencial ou arquivo real.
CREATE TABLE public."anexos" (
  "id" serial NOT NULL,
  "solicitacao_id" integer,
  "nome_arquivo" character varying,
  "caminho_arquivo" character varying,
  "tipo" character varying,
  "data_upload" timestamp without time zone,
  "caminho" character varying,
  "responsavel" character varying
);
CREATE TABLE public."categorias" (
  "id" serial NOT NULL,
  "nome" character varying,
  "descricao" character varying,
  "limites" text
);
CREATE TABLE public."checklist_envios_relatorios" (
  "id" serial NOT NULL,
  "execucao_id" integer NOT NULL,
  "dados_json" text NOT NULL,
  "status" character varying NOT NULL,
  "tentativas" integer NOT NULL,
  "ultimo_erro" text,
  "inicio_tentativa" character varying,
  "criado_em" character varying,
  "enviado_em" character varying
);
CREATE TABLE public."checklist_execucoes" (
  "id" serial NOT NULL,
  "item_id" integer NOT NULL,
  "responsavel" character varying NOT NULL,
  "status_conformidade" character varying,
  "observacao" text,
  "nome_foto" character varying,
  "caminho_foto" character varying,
  "data_execucao" character varying
);
CREATE TABLE public."checklist_itens" (
  "id" serial NOT NULL,
  "condominio" character varying NOT NULL,
  "titulo" character varying NOT NULL,
  "descricao_orientacao" text,
  "frequencia" character varying NOT NULL,
  "criado_em" character varying,
  "plano_acao_padrao" text,
  "condominio_id" integer
);
CREATE TABLE public."condominios" (
  "id" serial NOT NULL,
  "nome" character varying,
  "cnpj" character varying,
  "codigo" character varying
);
CREATE TABLE public."fornecedores" (
  "id" serial NOT NULL,
  "nome" character varying,
  "cnpj" character varying,
  "categoria" character varying
);
CREATE TABLE public."historico_solicitacoes" (
  "id" serial NOT NULL,
  "solicitacao_id" integer,
  "data" timestamp without time zone,
  "acao" character varying,
  "status_anterior" character varying,
  "status_novo" character varying,
  "responsavel" character varying,
  "descricao" character varying,
  "valor_anterior" double precision,
  "valor_novo" double precision,
  "observacao" character varying
);
CREATE TABLE public."limites_categoria_condominio" (
  "id" serial NOT NULL,
  "categoria_nome" character varying,
  "condominio_nome" character varying,
  "limite" double precision
);
CREATE TABLE public."playing_with_neon" (
  "id" serial NOT NULL,
  "name" text NOT NULL,
  "value" real
);
CREATE TABLE public."solicitacoes" (
  "id" serial NOT NULL,
  "numero" character varying,
  "condominio" character varying NOT NULL,
  "condominio_id" integer,
  "categoria" character varying NOT NULL,
  "fornecedor" character varying NOT NULL,
  "descricao" text NOT NULL,
  "valor_servico" double precision,
  "valor_produto" double precision,
  "valor" double precision,
  "valor_aprovado" double precision,
  "valor_realizado" double precision,
  "solicitante" character varying NOT NULL,
  "status" character varying,
  "motivo_ajuste" text,
  "observacao" text,
  "data" character varying
);
CREATE TABLE public."solicitacoes_compra" (
  "id" serial NOT NULL,
  "numero" character varying,
  "solicitante" character varying,
  "condominio" character varying,
  "categoria" character varying,
  "descricao" character varying,
  "fornecedor" character varying,
  "valor_servico" double precision,
  "valor_produto" double precision,
  "valor" double precision,
  "observacao" character varying,
  "valor_aprovado" double precision,
  "tipo_aprovacao" character varying,
  "valor_realizado" double precision,
  "data_inicio_execucao" timestamp without time zone,
  "data_finalizacao" timestamp without time zone,
  "observacao_execucao" character varying,
  "prioridade" character varying,
  "status" character varying,
  "motivo_ajuste" character varying,
  "data" timestamp without time zone
);
CREATE TABLE public."unidades" (
  "id" serial NOT NULL,
  "condominio_id" integer NOT NULL,
  "identificacao" character varying NOT NULL,
  "fracao_ideal" double precision
);
CREATE TABLE public."usuarios" (
  "id" serial NOT NULL,
  "nome" character varying,
  "email" character varying,
  "senha" character varying,
  "perfil" character varying,
  "condominio_id" integer
);
ALTER TABLE public."anexos" ADD CONSTRAINT "anexos_pkey" PRIMARY KEY (id);
ALTER TABLE public."anexos" ADD CONSTRAINT "anexos_solicitacao_id_fkey" FOREIGN KEY (solicitacao_id) REFERENCES solicitacoes_compra(id);
ALTER TABLE public."categorias" ADD CONSTRAINT "categorias_pkey" PRIMARY KEY (id);
ALTER TABLE public."checklist_envios_relatorios" ADD CONSTRAINT "checklist_envios_relatorios_pkey" PRIMARY KEY (id);
ALTER TABLE public."checklist_execucoes" ADD CONSTRAINT "checklist_execucoes_item_id_fkey" FOREIGN KEY (item_id) REFERENCES checklist_itens(id);
ALTER TABLE public."checklist_execucoes" ADD CONSTRAINT "checklist_execucoes_pkey" PRIMARY KEY (id);
ALTER TABLE public."checklist_itens" ADD CONSTRAINT "checklist_itens_pkey" PRIMARY KEY (id);
ALTER TABLE public."condominios" ADD CONSTRAINT "condominios_pkey" PRIMARY KEY (id);
ALTER TABLE public."fornecedores" ADD CONSTRAINT "fornecedores_pkey" PRIMARY KEY (id);
ALTER TABLE public."historico_solicitacoes" ADD CONSTRAINT "historico_solicitacoes_pkey" PRIMARY KEY (id);
ALTER TABLE public."historico_solicitacoes" ADD CONSTRAINT "historico_solicitacoes_solicitacao_id_fkey" FOREIGN KEY (solicitacao_id) REFERENCES solicitacoes_compra(id);
ALTER TABLE public."limites_categoria_condominio" ADD CONSTRAINT "limites_categoria_condominio_pkey" PRIMARY KEY (id);
ALTER TABLE public."playing_with_neon" ADD CONSTRAINT "playing_with_neon_pkey" PRIMARY KEY (id);
ALTER TABLE public."solicitacoes" ADD CONSTRAINT "solicitacoes_condominio_id_fkey" FOREIGN KEY (condominio_id) REFERENCES condominios(id);
ALTER TABLE public."solicitacoes" ADD CONSTRAINT "solicitacoes_pkey" PRIMARY KEY (id);
ALTER TABLE public."solicitacoes_compra" ADD CONSTRAINT "solicitacoes_compra_pkey" PRIMARY KEY (id);
ALTER TABLE public."unidades" ADD CONSTRAINT "unidades_condominio_id_fkey" FOREIGN KEY (condominio_id) REFERENCES condominios(id);
ALTER TABLE public."unidades" ADD CONSTRAINT "unidades_pkey" PRIMARY KEY (id);
ALTER TABLE public."usuarios" ADD CONSTRAINT "usuarios_pkey" PRIMARY KEY (id);
CREATE INDEX ix_anexos_id ON public.anexos USING btree (id);
CREATE INDEX ix_categorias_id ON public.categorias USING btree (id);
CREATE UNIQUE INDEX ix_categorias_nome ON public.categorias USING btree (nome);
CREATE UNIQUE INDEX ix_checklist_envios_relatorios_execucao_id ON public.checklist_envios_relatorios USING btree (execucao_id);
CREATE INDEX ix_checklist_envios_relatorios_id ON public.checklist_envios_relatorios USING btree (id);
CREATE INDEX ix_checklist_execucoes_id ON public.checklist_execucoes USING btree (id);
CREATE INDEX ix_checklist_itens_condominio_id ON public.checklist_itens USING btree (condominio_id);
CREATE INDEX ix_checklist_itens_id ON public.checklist_itens USING btree (id);
CREATE INDEX ix_condominios_id ON public.condominios USING btree (id);
CREATE UNIQUE INDEX ix_condominios_nome ON public.condominios USING btree (nome);
CREATE INDEX ix_fornecedores_id ON public.fornecedores USING btree (id);
CREATE UNIQUE INDEX ix_fornecedores_nome ON public.fornecedores USING btree (nome);
CREATE INDEX ix_historico_solicitacoes_id ON public.historico_solicitacoes USING btree (id);
CREATE INDEX ix_limites_categoria_condominio_categoria_nome ON public.limites_categoria_condominio USING btree (categoria_nome);
CREATE INDEX ix_limites_categoria_condominio_condominio_nome ON public.limites_categoria_condominio USING btree (condominio_nome);
CREATE INDEX ix_limites_categoria_condominio_id ON public.limites_categoria_condominio USING btree (id);
CREATE INDEX ix_solicitacoes_id ON public.solicitacoes USING btree (id);
CREATE UNIQUE INDEX ix_solicitacoes_numero ON public.solicitacoes USING btree (numero);
CREATE INDEX ix_solicitacoes_compra_id ON public.solicitacoes_compra USING btree (id);
CREATE UNIQUE INDEX ix_solicitacoes_compra_numero ON public.solicitacoes_compra USING btree (numero);
CREATE INDEX ix_unidades_id ON public.unidades USING btree (id);
CREATE INDEX ix_usuarios_condominio_id ON public.usuarios USING btree (condominio_id);
CREATE UNIQUE INDEX ix_usuarios_email ON public.usuarios USING btree (email);
CREATE INDEX ix_usuarios_id ON public.usuarios USING btree (id);
CREATE INDEX ix_usuarios_nome ON public.usuarios USING btree (nome);
CREATE UNIQUE INDEX ux_usuarios_checklist_condominio ON public.usuarios USING btree (condominio_id) WHERE (((perfil)::text = 'Checklist'::text) AND (condominio_id IS NOT NULL));
