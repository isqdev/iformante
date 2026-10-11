import {redirect} from "next/navigation";
export default async function Page({params}: {params: Promise<{documentId: string}>}) {const {documentId} = await params; redirect(`/docs?document=${encodeURIComponent(documentId)}`);}
