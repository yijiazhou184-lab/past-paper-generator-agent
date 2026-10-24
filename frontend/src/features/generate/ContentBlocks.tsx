import katex from "katex";
import "katex/dist/katex.min.css";
export type Block = {type:"text";text:string}|{type:"math";latex:string;display:boolean}
  |{type:"table";columns:string[];rows:string[][];caption:string}|{type:"asset_ref";asset_id:string};
export type Asset = {id:string;svg:string;alt:string};
export function ContentBlocks({blocks,assets=[]}:{blocks:Block[];assets?:Asset[]}) {
  return <>{blocks.map((block,index)=>{
    if(block.type==="text") return <p className="content-text" key={index}>{block.text}</p>;
    if(block.type==="math") {
      try {return <div key={index} className="content-math" dangerouslySetInnerHTML={{__html:katex.renderToString(block.latex,
        {displayMode:block.display,throwOnError:true,trust:false,strict:"warn",maxExpand:1000,maxSize:20})}}/>;}
      catch {return <p key={index} className="math-error" role="note">Formula could not be rendered: <code>{block.latex}</code></p>;}
    }
    if(block.type==="table") return <div className="content-table" key={index}><table><caption>{block.caption}</caption><thead><tr>{block.columns.map((c,i)=><th key={i} scope="col">{c}</th>)}</tr></thead>
      <tbody>{block.rows.map((row,i)=><tr key={i}>{row.map((value,j)=><td key={j}>{value}</td>)}</tr>)}</tbody></table></div>;
    const asset=assets.find(a=>a.id===block.asset_id);
    return asset ? <figure key={index}><img src={"data:image/svg+xml;charset=utf-8,"+encodeURIComponent(asset.svg)} alt={asset.alt}/><figcaption>{asset.alt}</figcaption></figure>
      : <p key={index} role="alert">A required diagram is unavailable.</p>;
  })}</>;
}
