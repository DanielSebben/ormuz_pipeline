# Por que este pipeline não faz scraping direto da UKMTO

A UKMTO (United Kingdom Maritime Trade Operations) não publica uma API
pública. Ela divulga "Advisories" e "Incident Reports" no próprio site
(ukmto.org) e por e-mail para navios cadastrados no esquema voluntário
de reporte (VRA).

O site também está configurado para bloquear rastreadores automatizados
via Cloudflare (retorna HTTP 403 para bots) — não é uma falha, é uma
decisão deliberada deles. Ou seja: tentar raspar ukmto.org programa-
ticamente não é só uma questão de termos de uso, na prática o pedido
provavelmente nem vai completar.

## Alternativas legítimas, em ordem de custo

1. **Cobertura via GDELT (gratuita)** — é o que este pipeline usa.
   Agências de notícia (Reuters, AP, gCaptain, etc.) reportam os
   alertas da UKMTO minutos depois de emitidos, e o GDELT indexa essa
   cobertura. É indireto, mas cobre a maioria dos eventos relevantes
   para precificação de mercado.

2. **Boletins públicos de outras autoridades marítimas** — a Marinha
   dos EUA (ONI, "Worldwide Threat to Shipping"), o NGA
   (msi.nga.mil/NavWarnings) e a CMF (Combined Maritime Forces)
   publicam avisos que frequentemente cobrem os mesmos incidentes.

3. **Provedores comerciais de inteligência marítima** (pagos, mas com
   acesso legítimo e dados de AIS de verdade) — Lloyd's List
   Intelligence, Windward, Dryad Global, MarineTraffic Pro. Esses
   dão o dado físico (o navio realmente mudou de rota / parou / foi
   atingido), que é mais confiável do que texto de manchete.

4. Se você quiser o dado oficial da própria UKMTO, o caminho correto é
   contatá-los para uma parceria de dados, não automatizar o acesso ao
   site.
