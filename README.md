Olá professor! 

Enquanto eu pensava à respeito do desafio, fiquei imaginando em resolver o input braçal

Então decidi fazer um leitor de arquivos, que transforma para as tabelas PG-SQL que criei

1 - Entidades (psycopg2)
(Consultar as propriedades na model.py)
Basicamente eu cadastro: Clubes, Elencos e Jogadores. onde fazemos:
1 Clube - N Elencos
1 Elenco - N Jogadores
Cada um tem seu respectivo CRUD

2 - Ingestão de arquivos (docling)
O docling permite que a gente envie vários tipos de arquivos (DOCX, XLSX, PDF, TXT, XML, JSON) e ele possa extrair o texto adequadamente para consumo de LLM.

3 - A interface (streamlit) 
Eu gosto muito de usar o streamlit para POC's e projetos menores, pois ela integra back-end e front-end
Tem a perda de ser server rendered, mas ele renderiza matplotlib e outros, então compensa demais.

4 - LLM (gemini 2.5 flash)
O prompt utilizado foi para trazer contexto sobre quais campos precisavamos extrair e como formatá-los para caber na tabela pgsql.



pode acessar via 
https://jogadores-footure-production.up.railway.app

