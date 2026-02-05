import Fastify from "fastify";
import multipart, { MultipartFile } from "@fastify/multipart";
import cors from "@fastify/cors";
import { v4 as uuidv4 } from "uuid";
import { env } from "./config";
import { supabaseClient } from "./supabaseClient";
import { UploadMetadata, UploadRecord } from "./types";

const app = Fastify({ logger: true });

await app.register(cors, { origin: true });
await app.register(multipart, { attachFieldsToBody: true });

app.get("/health", async () => ({ status: "ok", bucket: env.bucket }));

app.post("/upload", async (request, reply) => {
  const file = (await request.file()) as MultipartFile | undefined;
  if (!file) {
    return reply.status(400).send({ error: "Arquivo não fornecido" });
  }

  const metadataField = request.body?.metadata;
  let parsedMetadata: UploadMetadata = {};
  if (metadataField) {
    try {
      parsedMetadata = typeof metadataField === "string" ? JSON.parse(metadataField) : metadataField;
    } catch (error) {
      return reply.status(400).send({ error: "Campo 'metadata' precisa ser um JSON válido" });
    }
  }

  const destinationPath = `${uuidv4()}-${file.filename}`;
  const fileBuffer = await file.toBuffer();

  const { error: uploadError } = await supabaseClient.storage
    .from(env.bucket)
    .upload(destinationPath, fileBuffer, {
      cacheControl: "3600",
      upsert: false,
      contentType: file.mimetype ?? undefined
    });

  if (uploadError) {
    request.log.error(uploadError, "Falha ao subir arquivo para o bucket");
    return reply.status(502).send({ error: uploadError.message });
  }

  const insertPayload = {
    id: destinationPath,
    bucket: env.bucket,
    path: destinationPath,
    filename: file.filename,
    metadata: parsedMetadata
  };

  const { data: insertData, error: insertError } = await supabaseClient
    .from("uploads")
    .insert(insertPayload)
    .select()
    .single();

  if (insertError) {
    request.log.error(insertError, "Falha ao gravar metadados na tabela uploads");
    return reply.status(502).send({ error: insertError.message });
  }

  return reply.status(201).send(insertData);
});

app.get("/uploads", async (request) => {
  const { data, error } = await supabaseClient
    .from<UploadRecord>("uploads")
    .select("id,bucket,path,filename,metadata,created_at")
    .order("created_at", { ascending: false });

  if (error) {
    request.log.error(error, "Falha ao buscar uploads");
    return { data: [], error: error.message };
  }

  const withSignedUrls = await Promise.all(
    (data ?? []).map(async (record) => {
      const { data: signedUrlData } = await supabaseClient.storage
        .from(env.bucket)
        .createSignedUrl(record.path, env.signedUrlExpirationSeconds);

      return {
        ...record,
        signed_url: signedUrlData?.signedUrl
      };
    })
  );

  return { data: withSignedUrls, count: withSignedUrls.length };
});

const start = async () => {
  try {
    await app.listen({ port: env.port, host: "0.0.0.0" });
  } catch (error) {
    app.log.error(error);
    process.exit(1);
  }
};

void start();
